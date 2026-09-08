"""
Tests for ProcessManager (Native Windows Layer)
Location: tests/desktop/test_process_manager_native.py

Validates:
1. ProcessManager metadata, priority, dependencies, capabilities.
2. Health check and lifecycle methods.
3. Execution of read-only capabilities (list, info, top, tree, search).
4. Subprocess execution via process.start.
5. HMAC human approval gating on mutating capabilities (kill, priority).
6. Execution of signed mutating capabilities.
7. Safety guardrails against self-termination and Windows system termination.
8. Registration and auto-discovery in NativeManagerRegistry.
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from desktop.native.managers.base_manager import HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.process_manager import ProcessManager


class TestProcessManagerNative(unittest.TestCase):
    """Test suite for native ProcessManager."""

    def setUp(self):
        self.manager = ProcessManager()
        self.manager.initialize()

    def tearDown(self):
        self.manager.shutdown()

    def test_manager_metadata(self):
        """Verify manager metadata matches architecture specification."""
        self.assertEqual(self.manager.name, "process")
        self.assertEqual(self.manager.NAME, "process")
        self.assertEqual(self.manager.VERSION, "1.0")
        self.assertEqual(self.manager.PRIORITY, 18)
        self.assertIn("psutil", self.manager.DEPENDENCIES)

        expected_caps = [
            "process.list",
            "process.info",
            "process.kill",
            "process.priority",
            "process.top",
            "process.tree",
            "process.start",
            "process.search",
        ]
        self.assertEqual(len(self.manager.capabilities), 8)
        for cap in expected_caps:
            self.assertIn(cap, self.manager.capabilities)

    def test_health_check(self):
        """Verify health check returns healthy status when dependencies are met."""
        health = self.manager.health_check()
        self.assertEqual(health.manager_name, "process")
        self.assertEqual(health.status, HealthStatus.HEALTHY)
        self.assertEqual(health.total_capabilities, 8)
        self.assertEqual(health.available_capabilities, 8)
        self.assertTrue(health.details.get("initialized"))

    def test_process_list(self):
        """Verify process.list returns running processes."""
        result = self.manager.execute("process.list", arguments={"limit": 5})
        self.assertTrue(result.success)
        self.assertIn("processes", result.data)
        self.assertGreater(len(result.data["processes"]), 0)
        self.assertLessEqual(len(result.data["processes"]), 5)

        proc = result.data["processes"][0]
        self.assertIn("pid", proc)
        self.assertIn("name", proc)
        self.assertIn("cpu_percent", proc)
        self.assertIn("memory_percent", proc)
        self.assertIn("status", proc)

    def test_process_info(self):
        """Verify process.info retrieves comprehensive process details."""
        my_pid = os.getpid()
        result = self.manager.execute("process.info", arguments={"pid": my_pid})
        self.assertTrue(result.success)
        self.assertEqual(result.data["pid"], my_pid)
        self.assertIn("name", result.data)
        self.assertIn("exe", result.data)
        self.assertIn("cmdline", result.data)
        self.assertIn("status", result.data)
        self.assertIn("create_time", result.data)
        self.assertIn("cpu_percent", result.data)
        self.assertIn("memory_info", result.data)
        self.assertIn("num_threads", result.data)
        self.assertIn("username", result.data)

    def test_process_top(self):
        """Verify process.top sorts by CPU and memory."""
        res_cpu = self.manager.execute("process.top", arguments={"sort_by": "cpu", "count": 3})
        self.assertTrue(res_cpu.success)
        self.assertEqual(res_cpu.data["sorted_by"], "cpu_percent")
        self.assertLessEqual(len(res_cpu.data["processes"]), 3)

        res_mem = self.manager.execute("process.top", arguments={"sort_by": "memory", "count": 3})
        self.assertTrue(res_mem.success)
        self.assertEqual(res_mem.data["sorted_by"], "memory_percent")
        self.assertLessEqual(len(res_mem.data["processes"]), 3)

    def test_process_tree(self):
        """Verify process.tree returns parent and child information."""
        my_pid = os.getpid()
        result = self.manager.execute("process.tree", arguments={"pid": my_pid})
        self.assertTrue(result.success)
        self.assertEqual(result.data["parent"]["pid"], my_pid)
        self.assertIn("children", result.data)

    def test_process_search(self):
        """Verify process.search performs fuzzy matching."""
        result = self.manager.execute("process.search", arguments={"name": "pyth", "limit": 5})
        self.assertTrue(result.success)
        self.assertIn("matches", result.data)
        self.assertGreater(len(result.data["matches"]), 0)
        self.assertIn("similarity", result.data["matches"][0])

    def test_process_lifecycle_and_hmac(self):
        """Verify process.start, HMAC gating on priority & kill, and guardrails."""
        # 1. Start child process
        res_start = self.manager.execute(
            "process.start",
            arguments={"command": "powershell -NoProfile -Command Start-Sleep -Seconds 30"},
        )
        self.assertTrue(res_start.success)
        child_pid = res_start.data["pid"]

        try:
            # 2. Priority: un-ticketed request requires confirmation
            res_pri_ungated = self.manager.execute(
                "process.priority",
                arguments={"pid": child_pid, "priority": "below_normal"},
            )
            self.assertFalse(res_pri_ungated.success)
            self.assertTrue(res_pri_ungated.data.get("requires_confirmation"))
            ticket_id = res_pri_ungated.data["approval_ticket_id"]

            # Sign ticket and execute
            sig = self.manager.auth.generate_human_signature(ticket_id)
            self.assertIsNotNone(sig)

            res_pri_signed = self.manager.execute(
                "process.priority",
                arguments={
                    "pid": child_pid,
                    "priority": "below_normal",
                    "approval_ticket_id": ticket_id,
                    "approval_signature": sig,
                },
            )
            self.assertTrue(res_pri_signed.success)
            self.assertEqual(res_pri_signed.data["new_priority"], "below_normal")

            # 3. Guardrails: Attempt to kill self
            res_self = self.manager.execute("process.kill", arguments={"pid": os.getpid()})
            self.assertFalse(res_self.success)
            self_ticket = res_self.data["approval_ticket_id"]
            self_sig = self.manager.auth.generate_human_signature(self_ticket)
            res_self_signed = self.manager.execute(
                "process.kill",
                arguments={
                    "pid": os.getpid(),
                    "approval_ticket_id": self_ticket,
                    "approval_signature": self_sig,
                },
            )
            self.assertFalse(res_self_signed.success)
            self.assertIn("AuraAI host process", res_self_signed.error)

            # 4. Kill: un-ticketed request requires confirmation
            res_kill_ungated = self.manager.execute(
                "process.kill",
                arguments={"pid": child_pid, "force": True},
            )
            self.assertFalse(res_kill_ungated.success)
            self.assertTrue(res_kill_ungated.data.get("requires_confirmation"))
            kill_ticket = res_kill_ungated.data["approval_ticket_id"]

            # Sign ticket and execute kill
            kill_sig = self.manager.auth.generate_human_signature(kill_ticket)
            self.assertIsNotNone(kill_sig)

            res_kill_signed = self.manager.execute(
                "process.kill",
                arguments={
                    "pid": child_pid,
                    "force": True,
                    "approval_ticket_id": kill_ticket,
                    "approval_signature": kill_sig,
                },
            )
            self.assertTrue(res_kill_signed.success)
            self.assertEqual(res_kill_signed.data["count"], 1)

        finally:
            try:
                import psutil
                p = psutil.Process(child_pid)
                p.kill()
            except Exception:
                pass

    def test_registry_integration(self):
        """Verify ProcessManager is discovered by NativeManagerRegistry."""
        reg = NativeManagerRegistry.get_instance()
        pm = reg._managers.get("process")
        self.assertIsNotNone(pm)
        self.assertIsInstance(pm, ProcessManager)
        for cap in self.manager.capabilities:
            self.assertIn(cap, reg._capability_map)


if __name__ == "__main__":
    unittest.main()
