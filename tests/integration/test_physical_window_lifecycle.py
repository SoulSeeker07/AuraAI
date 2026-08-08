"""
Real Physical OS Integration Test — Desktop Window Lifecycle
Tests actual physical Win32 OS interaction:
Launch -> Verify HWND -> Minimize -> Verify IsIconic -> Restore -> Verify Visible -> Close -> Verify Destroyed
"""

import time

import win32gui

from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.orchestration.execution_policy import ExecutionPolicy
from desktop.native.desktop_execution_engine import reset_desktop_execution_engine


def test_real_notepad_window_lifecycle():
    reset_desktop_execution_engine()
    backend = DesktopEngineBackend()
    policy = ExecutionPolicy.get_instance()

    try:
        # 1. Launch Notepad
        res_launch = backend.execute(
            "app_open", "Open Notepad", {"app_name": "notepad"}
        )
        assert res_launch.success is True, f"Launch failed: {res_launch.observations}"
        time.sleep(0.5)

        # 2. Verify HWND exists via EnumWindows
        hwnds = policy._get_running_windows("notepad", None)
        assert len(hwnds) >= 1, "Expected at least 1 top-level Notepad HWND"
        main_hwnd = hwnds[0]
        assert bool(win32gui.IsWindowVisible(main_hwnd)) is True

        # 3. Minimize Notepad
        res_min = backend.execute(
            "window.minimize", "Minimize Notepad", {"app_name": "notepad"}
        )
        assert res_min.success is True
        time.sleep(0.3)

        # 4. Verify Iconic (Minimized)
        assert (
            bool(win32gui.IsIconic(main_hwnd)) is True
        ), "Expected window to be minimized (IsIconic)"

        # 5. Restore Notepad
        res_restore = backend.execute(
            "window.restore", "Restore Notepad", {"app_name": "notepad"}
        )
        assert res_restore.success is True
        time.sleep(0.3)

        # 6. Verify Visible & Not Iconic across application HWNDs
        notepad_hwnds = policy._get_running_windows("notepad", None)
        assert any(
            not bool(win32gui.IsIconic(h)) for h in notepad_hwnds
        ), "Expected Notepad window to be restored from icon"

        # 7. Close Notepad
        res_close = backend.execute(
            "app_close", "Close Notepad", {"app_name": "notepad"}
        )
        assert res_close.success is True
        time.sleep(1.0)

        # 8. Verify Destroyed / Process Closed
        hwnds_after = policy._get_running_windows("notepad", None)
        assert (
            len(hwnds_after) == 0
        ), f"Expected 0 Notepad windows remaining, found {len(hwnds_after)}"
    finally:
        reset_desktop_execution_engine()
        from desktop.native.managers.native_manager_registry import (
            NativeManagerRegistry,
        )

        NativeManagerRegistry.reset_instance()
