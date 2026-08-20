"""
Unit tests for DesktopResult status synchronization, DesktopBackend warning propagation,
and MiddlewareAction enum unification.
"""

from unittest.mock import MagicMock
import pytest

from src.desktop.native.desktop_result import DesktopResult, DesktopStatus
from src.desktop.native.middleware import MiddlewareAction, ExecutionResult as MiddlewareExecutionResult
from src.core.backends.adapters.desktop_backend import DesktopBackend
from src.core.planning.execution_result import ExecutionResult as CoreExecutionResult


def test_desktop_result_status_success_synchronization():
    """Verify bidirectional synchronization between success and status."""
    # 1. Default pending converts based on success
    res_succ = DesktopResult(success=True)
    assert res_succ.status == DesktopStatus.SUCCESS
    assert res_succ.success is True

    res_fail = DesktopResult(success=False)
    assert res_fail.status == DesktopStatus.FAILURE
    assert res_fail.success is False

    # 2. Explicit status overrides success appropriately
    res_partial = DesktopResult(success=False, status=DesktopStatus.PARTIAL)
    assert res_partial.status == DesktopStatus.PARTIAL
    assert res_partial.success is True  # Partial success is executable success

    res_cancelled = DesktopResult(success=True, status=DesktopStatus.CANCELLED)
    assert res_cancelled.status == DesktopStatus.CANCELLED
    assert res_cancelled.success is False

    res_failure = DesktopResult(success=True, status=DesktopStatus.FAILURE)
    assert res_failure.status == DesktopStatus.FAILURE
    assert res_failure.success is False


def test_middleware_action_enum_and_alias():
    """Verify MiddlewareAction enum and backward-compatibility alias."""
    assert MiddlewareAction.CONTINUE.value == "continue"
    assert MiddlewareAction.SKIP.value == "skip"
    assert MiddlewareAction.HALT.value == "halt"
    assert MiddlewareAction.ABORT.value == "abort"

    # Alias check
    assert MiddlewareExecutionResult is MiddlewareAction
    assert MiddlewareExecutionResult.CONTINUE is MiddlewareAction.CONTINUE


def test_desktop_backend_propagates_warnings_and_partial_status():
    """Verify DesktopBackend.execute propagates warnings and formats partial observations."""
    mock_engine = MagicMock()
    mock_engine.execute.return_value = DesktopResult(
        success=True,
        status=DesktopStatus.PARTIAL,
        data={"app_name": "notepad"},
        warnings=["Window was already open", "Secondary monitor unavailable"],
    )

    backend = DesktopBackend(engine=mock_engine)
    result = backend.execute("app_open", "open notepad", arguments={"app_name": "notepad"})

    assert isinstance(result, CoreExecutionResult)
    assert result.success is True
    assert len(result.warnings) == 2
    assert "Window was already open" in result.warnings
    assert "Secondary monitor unavailable" in result.warnings
    assert any("partially" in obs for obs in result.observations)
    assert any("Warnings:" in obs for obs in result.observations)


def test_desktop_backend_normal_success_warnings_empty():
    """Verify normal success without warnings produces clean output."""
    mock_engine = MagicMock()
    mock_engine.execute.return_value = DesktopResult(
        success=True,
        status=DesktopStatus.SUCCESS,
        data={"app_name": "notepad"},
        warnings=[],
    )

    backend = DesktopBackend(engine=mock_engine)
    result = backend.execute("app_open", "open notepad", arguments={"app_name": "notepad"})

    assert isinstance(result, CoreExecutionResult)
    assert result.success is True
    assert result.warnings == []
    assert any("open" in obs and "partially" not in obs for obs in result.observations)


def test_desktop_backend_app_name_fallback_compound_goals():
    """Verify DesktopBackend extracts correct app_name even with compound multi-word goals."""
    mock_engine = MagicMock()
    mock_engine.execute.return_value = DesktopResult(
        success=True,
        status=DesktopStatus.SUCCESS,
        data={"app_name": "notepad"},
    )

    backend = DesktopBackend(engine=mock_engine)

    # 1. Compound goal with conjunction & action verb
    backend.execute("app_open", goal="open notepad and write hello world", arguments={})
    assert backend._last_app_name == "notepad"

    # 2. Compound goal with 'and then' & stopword noise
    backend.execute("app_open", goal="open the chrome app and then search for weather", arguments={})
    assert backend._last_app_name == "chrome"

    # 3. Simple imperative with polite prefix
    backend.execute("app_open", goal="please launch discord", arguments={})
    assert backend._last_app_name == "discord"

    # 4. Explicit arguments override heuristic extraction
    backend.execute("app_open", goal="open something", arguments={"app_name": "spotify"})
    assert backend._last_app_name == "spotify"


def test_window_manager_undo_capabilities_and_verification():
    """Verify WindowManager returns DesktopResult with live rollback and passes engine verification."""
    from unittest.mock import patch
    from src.desktop.native.managers.window_manager import WindowManager
    from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine
    from src.desktop.native.capability_registry import CapabilityRegistry

    wm = WindowManager()
    engine = DesktopExecutionEngine()
    reg = CapabilityRegistry()

    # Mock win32 APIs so this test is deterministic in all environments
    with patch("win32gui.GetForegroundWindow", return_value=12345), \
         patch("win32gui.GetWindowRect", return_value=(100, 100, 500, 400)), \
         patch("win32gui.SetWindowPos", return_value=True), \
         patch("win32gui.ShowWindow", return_value=True), \
         patch("win32gui.IsWindow", return_value=True), \
         patch.object(wm, "_find_window", return_value=12345), \
         patch.object(wm, "_get_window_info", return_value={
             "title": "Notepad",
             "class_name": "Notepad",
             "process_id": 999,
             "process_name": "notepad.exe",
             "left": 100, "top": 100, "right": 500, "bottom": 400,
             "style": 0, "ex_style": 0
         }), \
         patch.object(wm, "_force_foreground", return_value=True):

        # 1. Test activate_window (supports_undo=True)
        res_act = wm.execute("window.activate", goal="activate Notepad", arguments={"window_title": "Notepad"})
        assert isinstance(res_act, DesktopResult)
        assert res_act.success is True
        assert res_act.rollback_available is True
        assert callable(res_act.rollback)
        assert "window_activated" in res_act.events

        # Verify through DesktopExecutionEngine._verify_result
        desc_act = reg.get("activate_window")
        ver_act = engine._verify_result(res_act, desc_act)
        assert ver_act["passed"] is True
        assert any(check["name"] == "rollback_available" and check["passed"] for check in ver_act["checks"])

        # Execute rollback and assert success
        assert res_act.execute_rollback() is True

        # 2. Test move_window (supports_undo=True)
        res_move = wm.execute("window.move", goal="move Notepad", arguments={"left": 200, "top": 200})
        assert isinstance(res_move, DesktopResult)
        assert res_move.success is True
        assert res_move.rollback_available is True
        assert res_move.execute_rollback() is True

        # 3. Test resize_window (supports_undo=True)
        res_resize = wm.execute("window.resize", goal="resize Notepad", arguments={"width": 800, "height": 600})
        assert isinstance(res_resize, DesktopResult)
        assert res_resize.success is True
        assert res_resize.rollback_available is True
        assert res_resize.execute_rollback() is True

        # 4. Test minimize_window (supports_undo=True)
        res_min = wm.execute("window.minimize", goal="minimize Notepad")
        assert isinstance(res_min, DesktopResult)
        assert res_min.success is True
        assert res_min.rollback_available is True
        assert res_min.execute_rollback() is True

        # 5. Test maximize_window (supports_undo=True)
        res_max = wm.execute("window.maximize", goal="maximize Notepad")
        assert isinstance(res_max, DesktopResult)
        assert res_max.success is True
        assert res_max.rollback_available is True
        assert res_max.execute_rollback() is True


def test_non_window_capabilities_observation_formatting():
    """Verify DesktopBackend generates clean, domain-specific observations without app/window template artifacts."""
    mock_engine = MagicMock()
    backend = DesktopBackend(engine=mock_engine)

    test_cases = [
        ("security.firewall_audit", "Inspect Windows Defender status and active firewall profile rules", {"firewall_status": "active"}),
        ("notification.send", "Display desktop notification confirming cross-domain pipeline completion", {"title": "Aura Alert", "message": "Pipeline finished"}),
        ("network.interface_list", "List all active network adapter interfaces", {"interfaces": ["Wi-Fi", "Ethernet"]}),
        ("clipboard.read_text", "Read current clipboard buffer text", {"text": "hello"}),
        ("display.get_brightness", "Get current monitor brightness level", {"brightness": 75}),
        ("finance.compute_metrics", "Compute EBITDA and CAGR revenue ratios", {"ebitda": 1500000}),
        ("system.status", "Query host system specs and CPU utilization", {"cpu": "Intel i9"}),
        ("keyboard.press", "Press enter key in editor", {"key": "enter"}),
    ]

    for cap, goal, data in test_cases:
        mock_engine.execute.return_value = DesktopResult(
            success=True,
            capability=cap,
            data=data,
            verification={"passed": True},
        )
        res = backend.execute(cap, goal=goal)
        assert res.success is True
        obs = res.observations[0]

        # Invariant: Observation must never contain window/app template artifacts
        assert " is open" not in obs, f"Garbled 'is open' found in observation for {cap}: {obs}"
        assert " is closed" not in obs, f"Garbled 'is closed' found in observation for {cap}: {obs}"
        assert " is focused" not in obs, f"Garbled 'is focused' found in observation for {cap}: {obs}"
        assert " is resized" not in obs, f"Garbled 'is resized' found in observation for {cap}: {obs}"
        assert " is moved" not in obs, f"Garbled 'is moved' found in observation for {cap}: {obs}"
        assert "Rules. is" not in obs, f"App extraction artifact found in observation for {cap}: {obs}"
        assert "Completion. is" not in obs, f"App extraction artifact found in observation for {cap}: {obs}"
        assert obs.startswith("✓") or obs.startswith("⚠"), f"Observation should start with status symbol: {obs}"


