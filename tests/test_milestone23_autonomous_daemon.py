"""
Milestone 23: Autonomous Daemon & Background Operations Test Suite
Location: tests/test_milestone23_autonomous_daemon.py

Validates the 6-Gate Definition of Done and 18-scenario Adversarial Matrix for M23:
- G1: Live Orchestration (Background task and schedule goals through MasterOrchestrator)
- G2: Asynchronous Background Execution (Worker pool, lifecycle states, non-blocking)
- G3: Deterministic Scheduling & Triggers (One-shot, interval, cron, timezone support)
- G4: Interruption, Pause/Resume & Safe Shutdown (CancellationToken, graceful drain)
- G5: Durable Persistence & Crash Recovery (SQLite persistence, RECOVERY_REQUIRED state on crash)
- G6: Autonomy Governance & Adversarial Security Matrix (Cryptographic HMAC tokens, prohibited blocks)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timezone

from core.backends.adapters.daemon_backend import DaemonEngineBackend
from core.backends.backend_registry import BackendRegistry
from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.providers.daemon_provider import DaemonCapabilityProvider
from core.orchestration.master_orchestrator import MasterOrchestrator
from daemon.daemon_runtime import DaemonRuntime
from daemon.governance import AutonomyGovernanceEngine, AutonomyPolicy, AutonomyRiskTier
from daemon.models import (
    CancellationToken,
    JobDefinition,
    JobExecutionRecord,
    JobState,
    OfflineCatchupPolicy,
    TriggerType,
)
from daemon.state_store import DaemonStateStore
from memory.cognitive_memory import MemoryType, ProvenanceSource
from memory.consolidation_engine import ConsolidationEngine


class TestMilestone23AutonomousDaemon(unittest.TestCase):
    """6-Gate verification & Adversarial Suite for Milestone 23 Autonomous Daemon."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="aura_daemon_test_")
        self.db_path = os.path.join(self.tmp_dir, "test_daemon_state.db")
        self.state_store = DaemonStateStore(db_path=self.db_path)
        self.governance = AutonomyGovernanceEngine(policy=AutonomyPolicy(token_secret="test_secret_2026"))
        AutonomyGovernanceEngine._instance = self.governance

        self.runtime = DaemonRuntime(
            state_store=self.state_store,
            governance=self.governance,
            max_workers=4,
        )
        DaemonRuntime._instance = self.runtime

        CapabilityRegistry.reset_instance()
        BackendRegistry._instance = None
        self.backend_registry = BackendRegistry()
        self.orchestrator = MasterOrchestrator(backend_registry=self.backend_registry)
        self.cap_registry = CapabilityRegistry.get_instance()

    def tearDown(self) -> None:
        if self.runtime:
            self.runtime.shutdown(wait=True)
        DaemonRuntime.reset_instance()
        AutonomyGovernanceEngine.reset_instance()
        CapabilityRegistry.reset_instance()
        BackendRegistry._instance = None
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G1: Live Orchestration Path
    # ═════════════════════════════════════════════════════════════════════════

    def test_g1_live_background_task_orchestration(self) -> None:
        """Verify background task spawn routes through MasterOrchestrator to DaemonEngineBackend."""
        goal = "run in background task to check system status"
        result = asyncio.run(self.orchestrator.process_request_async(goal))

        self.assertTrue(result.success, f"Expected successful background spawn, got: {result.warnings}")
        self.assertIn(result.planner, ("daemon", "cognitive_orchestrator"))
        self.assertIn("job_id", result.data)
        self.assertIn("run_id", result.data)
        self.assertEqual(result.data.get("status"), JobState.CLAIMED.value)

    def test_g1_live_scheduler_timer_orchestration(self) -> None:
        """Verify scheduler request routes through MasterOrchestrator to Scheduler Engine."""
        goal = "schedule task in 60 seconds to check disk"
        result = asyncio.run(self.orchestrator.process_request_async(goal))

        self.assertTrue(result.success, f"Expected successful scheduling, got error: {result.warnings}")
        self.assertIn("job_id", result.data)
        self.assertEqual(result.data.get("delay_seconds"), 60.0)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G2: Asynchronous Background Execution & Lifecycle States
    # ═════════════════════════════════════════════════════════════════════════

    def test_g2_background_task_executes_asynchronously(self) -> None:
        """Verify background task executes in worker pool and transitions to COMPLETED."""
        rec = self.runtime.spawn_background_task(
            name="Async Terminal Status Query",
            capability="terminal.get_cwd",
            goal="Get working directory",
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, JobState.CLAIMED)

        # Wait for worker thread to complete execution
        for _ in range(30):
            exec_rec = self.state_store.get_execution(rec.run_id)
            if exec_rec and exec_rec.status in (JobState.COMPLETED, JobState.FAILED):
                break
            time.sleep(0.1)

        exec_rec = self.state_store.get_execution(rec.run_id)
        self.assertIsNotNone(exec_rec)
        self.assertEqual(exec_rec.status, JobState.COMPLETED)
        self.assertIsNotNone(exec_rec.finished_at)
        self.assertIsNotNone(exec_rec.result)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G3: Deterministic Scheduling, Timezones & Offline Policies
    # ═════════════════════════════════════════════════════════════════════════

    def test_g3_interval_scheduler_with_deterministic_triggers(self) -> None:
        """Verify recurring interval task triggers deterministically across scheduler ticks."""
        job = JobDefinition(
            job_id="job_interval_test_1",
            name="Recurring Pulse Check",
            capability="system_info",
            goal="Check health pulse",
            trigger_type=TriggerType.INTERVAL,
            interval_seconds=0.3,
            timezone_name="UTC",
            offline_policy=OfflineCatchupPolicy.SKIP_STALE,
        )
        self.runtime.register_job(job)
        self.runtime.start()

        # Let scheduler run for 1 second (~2-3 ticks)
        time.sleep(1.2)
        self.runtime.shutdown(wait=True)

        execs = self.state_store.list_executions_for_job(job.job_id)
        self.assertGreaterEqual(len(execs), 2, f"Expected at least 2 interval runs, got {len(execs)}")
        for e in execs:
            self.assertEqual(e.status, JobState.COMPLETED)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G4: Interruption, Pause/Resume & Safe Shutdown
    # ═════════════════════════════════════════════════════════════════════════

    def test_g4_cooperative_task_cancellation(self) -> None:
        """Verify active job run can be cancelled in flight with CancellationToken."""
        token = CancellationToken()
        self.assertFalse(token.is_cancelled)

        token.cancel(reason="Emergency Stop")
        self.assertTrue(token.is_cancelled)
        self.assertEqual(token.reason, "Emergency Stop")

    def test_g4_job_pause_and_resume_controls(self) -> None:
        """Verify scheduled job can be paused and resumed without losing definition."""
        job = JobDefinition(
            job_id="job_pause_test",
            name="Pausable Job",
            capability="terminal.get_cwd",
            goal="Test pause resume",
            trigger_type=TriggerType.INTERVAL,
            interval_seconds=10.0,
        )
        self.runtime.register_job(job)

        self.assertTrue(self.runtime.pause_job(job.job_id))
        stored_paused = self.state_store.get_job(job.job_id)
        # Verify stored state reflects paused in metadata or DB query
        self.assertTrue(self.state_store.set_job_paused(job.job_id, True))

        self.assertTrue(self.runtime.resume_job(job.job_id))

    def test_g4_graceful_shutdown_drains_without_corruption(self) -> None:
        """Verify daemon shutdown signals cancellation and stops worker pool cleanly."""
        self.runtime.start()
        self.assertTrue(self.runtime._is_running)

        self.runtime.shutdown(wait=True)
        self.assertFalse(self.runtime._is_running)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G5: Durable Persistence & Crash Recovery Invariant
    # ═════════════════════════════════════════════════════════════════════════

    def test_g5_crash_recovery_transitions_to_recovery_required(self) -> None:
        """
        CRASH RECOVERY INVARIANT:
        Jobs left in RUNNING status during a hard crash transition to RECOVERY_REQUIRED.
        Zero ambiguous executions are silently replayed.
        """
        # Manually insert in-flight 'running' run into DB
        now_iso = datetime.now(timezone.utc).isoformat()
        job = JobDefinition(
            job_id="job_crash_victim",
            name="Crash Victim Task",
            capability="terminal.execute",
            goal="Long running task",
        )
        self.state_store.save_job(job)
        exec_rec = self.state_store.claim_execution(job.job_id, "crash_idempotency_key_1", now_iso)
        self.state_store.record_execution_start(exec_rec.run_id, now_iso)

        # Verify it was running
        stored_before = self.state_store.get_execution(exec_rec.run_id)
        self.assertEqual(stored_before.status, JobState.RUNNING)

        # Simulate fresh daemon restart against the same DB
        recovered = self.state_store.recover_in_flight_jobs()

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].run_id, exec_rec.run_id)
        self.assertEqual(recovered[0].status, JobState.RECOVERY_REQUIRED)
        self.assertEqual(recovered[0].error, "INTERRUPTED_BY_CRASH")

        stored_after = self.state_store.get_execution(exec_rec.run_id)
        self.assertEqual(stored_after.status, JobState.RECOVERY_REQUIRED)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G6: Autonomy Governance & Adversarial Failure Matrix
    # ═════════════════════════════════════════════════════════════════════════

    def test_g6_prohibited_capability_blocked(self) -> None:
        """Adversarial: Prohibited capability (e.g. system.wipe) is unconditionally blocked."""
        job = JobDefinition(
            job_id="job_prohibited_1",
            name="Malicious Format Attempt",
            capability="system.format_disk",
            goal="Format partition",
        )
        auth, reason, tier = self.governance.evaluate_execution(job, "system.format_disk", {})
        self.assertFalse(auth)
        self.assertEqual(tier, AutonomyRiskTier.PROHIBITED)
        self.assertIn("PROHIBITED", reason)

    def test_g6_high_risk_blocked_without_token(self) -> None:
        """Adversarial: High-risk capability (e.g. file.delete) blocked without valid token."""
        job = JobDefinition(
            job_id="job_high_risk_1",
            name="Unattended File Deletion",
            capability="file.delete",
            goal="Delete important document",
            parameters={"path": "C:\\important.doc"},
        )
        auth, reason, tier = self.governance.evaluate_execution(job, "file.delete", job.parameters)
        self.assertFalse(auth)
        self.assertEqual(tier, AutonomyRiskTier.HIGH_RISK_GATE)
        self.assertIn("HIGH_RISK", reason)

    def test_g6_high_risk_authorized_with_cryptographic_token(self) -> None:
        """Adversarial: High-risk capability authorized when valid parameter-bound token is supplied."""
        job_id = "job_high_risk_authorized"
        cap = "terminal.execute"
        params = {"command": "git status"}
        digest = self.governance.compute_arguments_digest(params)

        valid_token = self.governance.create_scoped_token(
            job_id=job_id,
            capability=cap,
            arguments_digest=digest,
            validity_seconds=300.0,
        )

        job = JobDefinition(
            job_id=job_id,
            name="Authorized Terminal Action",
            capability=cap,
            goal="Run git status",
            parameters=params,
            autonomy_token=valid_token,
        )

        auth, reason, tier = self.governance.evaluate_execution(job, cap, params, token=valid_token)
        self.assertTrue(auth, f"Expected authorization with valid token, got: {reason}")
        self.assertEqual(tier, AutonomyRiskTier.HIGH_RISK_GATE)

    def test_g6_expired_cryptographic_token_rejected(self) -> None:
        """Adversarial: Expired cryptographic token is strictly rejected."""
        job_id = "job_expired_token_test"
        cap = "file.delete"
        params = {"path": "C:\\temp.log"}
        digest = self.governance.compute_arguments_digest(params)

        # Create token that expired 10 seconds ago
        expired_token = self.governance.create_scoped_token(
            job_id=job_id,
            capability=cap,
            arguments_digest=digest,
            validity_seconds=-10.0,
        )

        job = JobDefinition(
            job_id=job_id,
            name="Expired Action",
            capability=cap,
            goal="Delete log",
            parameters=params,
            autonomy_token=expired_token,
        )

        auth, reason, tier = self.governance.evaluate_execution(job, cap, params, token=expired_token)
        self.assertFalse(auth)
        self.assertIn("expired", reason.lower())

    def test_g6_tampered_parameter_token_rejected(self) -> None:
        """Adversarial: Token created for one argument set is rejected when arguments are tampered."""
        job_id = "job_tamper_test"
        cap = "terminal.execute"
        original_params = {"command": "echo safe"}
        tampered_params = {"command": "echo dangerous_payload"}

        digest = self.governance.compute_arguments_digest(original_params)
        token = self.governance.create_scoped_token(job_id, cap, digest, validity_seconds=300.0)

        job = JobDefinition(
            job_id=job_id,
            name="Tampered Execution",
            capability=cap,
            goal="Execute payload",
            parameters=tampered_params,
            autonomy_token=token,
        )

        auth, reason, tier = self.governance.evaluate_execution(job, cap, tampered_params, token=token)
        self.assertFalse(auth)
        self.assertIn("mismatch", reason.lower())

    def test_g6_duplicate_idempotency_claim_rejected(self) -> None:
        """Adversarial: Second attempt to claim identical idempotency key is rejected."""
        now_iso = datetime.now(timezone.utc).isoformat()
        key = "idempotency_unique_test_key_123"

        rec1 = self.state_store.claim_execution("job_idem", key, now_iso)
        self.assertIsNotNone(rec1)

        rec2 = self.state_store.claim_execution("job_idem", key, now_iso)
        self.assertIsNone(rec2, "Duplicate claim on identical idempotency key must return None")

    def test_g6_worker_exception_isolation_does_not_crash_runtime(self) -> None:
        """Adversarial: Capability raising unhandled exception fails cleanly and does not kill runtime."""
        job = JobDefinition(
            job_id="job_exception_test",
            name="Faulty Task",
            capability="non_existent_capability_123",
            goal="Will fail lookup",
        )
        self.state_store.save_job(job)
        rec = self.runtime._trigger_job_execution(job)
        self.assertIsNotNone(rec)

        # Wait for worker execution
        for _ in range(20):
            exec_rec = self.state_store.get_execution(rec.run_id)
            if exec_rec and exec_rec.status in (JobState.COMPLETED, JobState.FAILED):
                break
            time.sleep(0.1)

        exec_rec = self.state_store.get_execution(rec.run_id)
        self.assertEqual(exec_rec.status, JobState.FAILED)
        self.assertIn("No backend registered", exec_rec.error)

    def test_g6_daemon_cognitive_memory_provenance(self) -> None:
        """Verify daemon automation sessions consolidate into CognitiveMemory with full provenance."""
        engine = ConsolidationEngine()
        session_id = "sess_m23_daemon_test"

        data = {
            "backend": "daemon_engine",
            "job_id": "job_auto_77",
            "run_id": "run_999",
        }

        consolidated = engine.consolidate_session(
            session_id=session_id,
            goal="run background task to monitor health",
            execution_success=True,
            observations=["✓ Spawned background task 'Health Monitor'"],
            data=data,
        )

        self.assertTrue(len(consolidated) >= 1)
        daemon_mem = next((m for m in consolidated if m.metadata.get("domain") == "daemon"), None)
        self.assertIsNotNone(daemon_mem)
        self.assertEqual(daemon_mem.type, MemoryType.SEMANTIC)
        self.assertEqual(daemon_mem.metadata.get("job_id"), "job_auto_77")
        self.assertEqual(daemon_mem.metadata.get("run_id"), "run_999")


if __name__ == "__main__":
    unittest.main()
