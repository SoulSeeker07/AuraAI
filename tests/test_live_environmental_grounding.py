"""
Comprehensive Real Environment Test Suite for Phases 3, 4, and 5
(Testing REAL screen capture/OCR, REAL Personal OS DB, REAL Win32 clipboard, and REAL system telemetry)
"""

import sys
import asyncio
from pathlib import Path

# Add src and root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(1, str(PROJECT_ROOT))

from core.tools.aura_tool_registry import AuraToolRegistry
from core.aura_core import AuraCore


def test_real_vision_screen_inspection():
    """Phase 3: Verify real screen capture and OCR on the running Windows system."""
    async def _run():
        res = await AuraToolRegistry.execute_tool("vision_inspect_screen", {})
        print(f"Vision Tool Execution Result: {res}")
        assert res.get("status") == "success", f"Vision inspection failed: {res}"
        assert "active_window" in res
        assert len(res["active_window"]) > 0
        assert "visible_text" in res

    asyncio.run(_run())


def test_real_personal_os_agenda_and_tasks():
    """Phase 4: Verify real Personal OS task creation and daily agenda synthesis."""
    async def _run():
        core = AuraCore.get_instance()
        # 1. Add task
        add_res = await AuraToolRegistry.execute_tool(
            "personal_os_add_task",
            {"title": "Verify Cognitive Intelligence v17", "priority": 1},
            aura_core=core,
        )
        assert add_res.get("status") == "success"
        assert "Verify Cognitive Intelligence v17" in add_res.get("message", "")

        # 2. Get daily agenda
        agenda_res = await AuraToolRegistry.execute_tool(
            "personal_os_get_daily_agenda",
            {},
            aura_core=core,
        )
        assert agenda_res.get("status") == "success"
        assert "date" in agenda_res
        assert "summary" in agenda_res

    asyncio.run(_run())


def test_real_hardware_telemetry():
    """Phase 5: Verify real hardware telemetry (CPU, RAM, OS, Battery)."""
    async def _run():
        res = await AuraToolRegistry.execute_tool("system_get_telemetry", {})
        assert res.get("status") == "success"
        assert "%" in res.get("cpu_usage", "")
        assert "MB" in res.get("ram_usage", "")
        assert "Windows" in res.get("os", "")

    asyncio.run(_run())


def test_real_win32_clipboard_roundtrip():
    """Phase 5: Verify real Win32 clipboard write and read."""
    async def _run():
        test_payload = "AuraAI-Autonomous-Test-Payload-12345"
        # Write
        write_res = await AuraToolRegistry.execute_tool(
            "desktop_clipboard",
            {"action": "write", "text": test_payload},
        )
        assert write_res.get("status") == "success"

        # Read
        read_res = await AuraToolRegistry.execute_tool(
            "desktop_clipboard",
            {"action": "read"},
        )
        assert read_res.get("status") == "success"
        assert read_res.get("content") == test_payload

    asyncio.run(_run())


if __name__ == "__main__":
    print("--- Running Real Phase 3 Screen Inspection Test ---")
    test_real_vision_screen_inspection()
    print("✓ Real Screen Inspection PASSED")

    print("\n--- Running Real Phase 4 Personal OS Task & Agenda Test ---")
    test_real_personal_os_agenda_and_tasks()
    print("✓ Real Personal OS Task & Agenda PASSED")

    print("\n--- Running Real Phase 5 Hardware Telemetry Test ---")
    test_real_hardware_telemetry()
    print("✓ Real Hardware Telemetry PASSED")

    print("\n--- Running Real Phase 5 Win32 Clipboard Roundtrip Test ---")
    test_real_win32_clipboard_roundtrip()
    print("✓ Real Win32 Clipboard Roundtrip PASSED")

    print("\n🎉 ALL REAL ENVIRONMENT TESTS (PHASES 3, 4, 5) PASSED WITH FLYING COLORS!")
