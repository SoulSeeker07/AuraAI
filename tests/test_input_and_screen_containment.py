"""
Unit & Adversarial Tests for InputManager and ScreenActionManager Containment
Location: tests/test_input_and_screen_containment.py
"""

from unittest.mock import MagicMock, patch
import pytest

from desktop.native.managers.input_manager import InputFailsafeException, InputManager
from desktop.native.managers.screen_action_manager import ScreenActionManager


class TestInputManagerContainment:
    """Tests for InputManager hardware failsafes, coordinate clamping, and sticky-key prevention."""

    def test_input_coordinate_clamping(self):
        mgr = InputManager()
        cx, cy = mgr._clamp_coords(-50, 99999)
        assert cx == 0
        assert cy > 0
        assert cy < 99999

    def test_input_failsafe_corner_trap_trigger(self):
        mgr = InputManager()
        # Mock cursor position to corner (0, 0)
        with patch.object(mgr, "_mouse_position", return_value=(0, 0)):
            with pytest.raises(InputFailsafeException) as exc_info:
                mgr._check_failsafe()
            assert "Input failsafe triggered" in str(exc_info.value)
            assert mgr._emergency_aborted is True

    def test_input_failsafe_disabled_does_not_abort(self):
        mgr = InputManager()
        mgr.failsafe_enabled = False
        with patch.object(mgr, "_mouse_position", return_value=(0, 0)):
            mgr._check_failsafe()  # Should not raise

    def test_input_emergency_stop_capability(self):
        mgr = InputManager()
        mgr.initialize()
        mgr._held_keys.add(0xA2)  # VK_CONTROL
        res = mgr.execute("input.emergency_stop")
        assert res.success is True
        assert res.data["emergency_stop"] is True
        assert len(mgr._held_keys) == 0

    def test_input_release_held_keys_capability(self):
        mgr = InputManager()
        mgr.initialize()
        mgr._held_keys.add(0xA0)  # VK_SHIFT
        res = mgr.execute("input.release_held_keys")
        assert res.success is True
        assert res.data["released"] is True
        assert len(mgr._held_keys) == 0


    def test_input_drag_failsafe_triggered_mid_interpolation(self):
        mgr = InputManager()
        mgr.initialize()

        # Fail on the 3rd interpolation step
        call_count = 0

        def dynamic_mouse_pos():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return (0, 0)
            return (500, 500)

        with patch.object(mgr, "_mouse_position", side_effect=dynamic_mouse_pos):
            with pytest.raises(InputFailsafeException):
                mgr._drag(100, 100, 400, 400, duration=0.1)


class TestScreenActionManagerContainment:
    """Tests for ScreenActionManager default window bounding box containment and boundary jails."""

    def test_screen_act_step_default_foreground_window_boundary_enforcement(self):
        mgr = ScreenActionManager()
        mgr.initialize()

        # Mock GetForegroundWindow and GetWindowRect to return a known bounding box (200, 200, 600, 500)
        with patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999):
            with patch("ctypes.windll.user32.GetWindowRect") as mock_rect:
                def set_rect(hwnd, ref):
                    ref._obj.left = 200
                    ref._obj.top = 200
                    ref._obj.right = 600
                    ref._obj.bottom = 500
                    return 1

                mock_rect.side_effect = set_rect
                # Test click outside window boundary (e.g. at 50, 50) without passing window_title
                res = mgr.execute(
                    "screen.act_step",
                    arguments={"action": "click", "x": 50, "y": 50},  # No window_title -> defaults to active window
                )
                assert res.success is False
                assert "Window Boundary Violation" in res.error

    def test_screen_act_step_explicit_fullscreen_allowed(self):
        mgr = ScreenActionManager()
        mgr.initialize()

        with patch("ctypes.windll.user32.GetForegroundWindow", return_value=99999):
            with patch("ctypes.windll.user32.GetWindowRect") as mock_rect:
                def set_rect(hwnd, ref):
                    ref._obj.left = 200
                    ref._obj.top = 200
                    ref._obj.right = 600
                    ref._obj.bottom = 500
                    return 1

                mock_rect.side_effect = set_rect
                # Explicit full-screen override
                res = mgr.execute(
                    "screen.act_step",
                    arguments={"action": "click", "x": 50, "y": 50, "allow_fullscreen": True},
                )
                assert res.success is True

