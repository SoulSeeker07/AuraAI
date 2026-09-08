'''
Tests for AuraToolRegistry Desktop Primitives Delegation to NativeManagerRegistry

Verifies that _launch_app, _control_window, _set_volume, _set_brightness,
and _handle_clipboard route through governed NativeManagerRegistry managers,
preserving safety constraints and falling back safely if managers are unavailable.
'''

from unittest.mock import MagicMock, patch
import pytest

from core.tools.aura_tool_registry import AuraToolRegistry
from desktop.native.desktop_result import DesktopResult


class TestAuraToolRegistryDelegation:
    '''Test suite asserting AuraToolRegistry desktop primitive delegation.'''
    def test_launch_app_delegates_to_window_manager(self):
        mock_win_mgr = MagicMock()
        mock_win_mgr.execute.return_value = DesktopResult.create_success(
            goal="launch notepad",
            capability="app_open",
            manager="window",
            data={"reused": False, "app_name": "notepad"},
        )

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_win_mgr
            res = AuraToolRegistry._launch_app("notepad")
            assert res["status"] == "success"
            assert "Launched 'notepad' successfully" in res["message"]
            mock_win_mgr.execute.assert_called_once_with(
                "app_open", app_name="notepad", goal="launch notepad"
            )

    def test_launch_app_reports_window_reuse(self):
        mock_win_mgr = MagicMock()
        mock_win_mgr.execute.return_value = DesktopResult.create_success(
            goal="launch chrome",
            capability="app_open",
            manager="window",
            data={"reused": True, "app_name": "chrome"},
        )

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_win_mgr
            res = AuraToolRegistry._launch_app("chrome")
            assert res["status"] == "success"
            assert "Switched to existing window for 'chrome'" in res["message"]

    def test_launch_app_fallback_on_window_manager_failure(self):
        mock_win_mgr = MagicMock()
        mock_win_mgr.execute.return_value = DesktopResult.create_failure(
            goal="launch custom_tool",
            capability="app_open",
            manager="window",
            error="Application not found",
        )

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg, patch("subprocess.Popen") as mock_popen:
            mock_reg.return_value.get_manager.return_value = mock_win_mgr
            res = AuraToolRegistry._launch_app("custom_tool --flag")
            assert res["status"] == "success"
            assert "Launched 'custom_tool --flag' successfully" in res["message"]
            mock_popen.assert_called_once_with("custom_tool --flag", shell=True)

    def test_control_window_invalid_action(self):
        res = AuraToolRegistry._control_window("My Window", "dance")
        assert res["status"] == "error"
        assert "Unknown window action: dance" in res["message"]

    def test_control_window_nonexistent_window_error(self):
        mock_win_mgr = MagicMock()
        mock_win_mgr._find_window.return_value = None

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_win_mgr
            res = AuraToolRegistry._control_window("NonexistentWindow9999", "focus")
            assert res["status"] == "error"
            assert "No active window found matching 'NonexistentWindow9999'" in res["message"]
            mock_win_mgr.execute.assert_not_called()

    @pytest.mark.parametrize(
        "action,capability,expected_verb",
        [
            ("focus", "window.activate", "Brought window 'Test Editor' to the foreground."),
            ("minimize", "window.minimize", "Minimized window 'Test Editor'."),
            ("maximize", "window.maximize", "Maximized window 'Test Editor'."),
            ("restore", "window.restore", "Restored window 'Test Editor'."),
            ("close", "window.close", "Closed window 'Test Editor'."),
        ],
    )
    def test_control_window_delegation_actions(self, action, capability, expected_verb):
        mock_win_mgr = MagicMock()
        mock_win_mgr._find_window.return_value = 12345
        mock_win_mgr.execute.return_value = DesktopResult.create_success(
            goal=f"{action} Test Editor",
            capability=capability,
            manager="window",
            data={"window_title": "Test Editor", "window_handle": 12345},
        )

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_win_mgr
            res = AuraToolRegistry._control_window("Test Editor", action)
            assert res["status"] == "success"
            assert res["message"] == expected_verb
            mock_win_mgr.execute.assert_called_once_with(
                capability,
                window_title="Test Editor",
                window_handle=12345,
                goal=f"{action} Test Editor",
            )

    def test_clipboard_delegation_read_and_write(self):
        mock_cb_mgr = MagicMock()
        mock_cb_mgr.execute.side_effect = [
            DesktopResult.create_success(
                goal="write clipboard",
                capability="clipboard.write_text",
                manager="clipboard",
                data={"text": "hello aura"},
            ),
            DesktopResult.create_success(
                goal="read clipboard",
                capability="clipboard.read_text",
                manager="clipboard",
                data={"text": "hello aura"},
            ),
        ]

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_cb_mgr
            write_res = AuraToolRegistry._handle_clipboard("write", "hello aura")
            assert write_res["status"] == "success"
            assert "Copied text to clipboard" in write_res["message"]

            read_res = AuraToolRegistry._handle_clipboard("read")
            assert read_res["status"] == "success"
            assert read_res["content"] == "hello aura"

    def test_clipboard_invalid_action(self):
        res = AuraToolRegistry._handle_clipboard("paste_magic")
        assert res["status"] == "error"
        assert "Invalid clipboard action: paste_magic" in res["message"]

    def test_set_volume_delegation(self):
        mock_audio_mgr = MagicMock()
        mock_audio_mgr.execute.side_effect = [
            DesktopResult.create_success(
                goal="toggle mute",
                capability="audio.toggle_mute",
                manager="audio",
                data={"muted": False},
            ),
            DesktopResult.create_success(
                goal="set volume",
                capability="audio.set_volume",
                manager="audio",
                data={"level": 75.0},
            ),
        ]

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_audio_mgr
            res = AuraToolRegistry._set_volume(level=75, mute=False)
            assert res["status"] == "success"
            assert res["message"] == "Audio unmuted, volume set to 75%"
            assert mock_audio_mgr.execute.call_count == 2

    def test_set_brightness_delegation(self):
        mock_disp_mgr = MagicMock()
        mock_disp_mgr.execute.return_value = DesktopResult.create_success(
            goal="set brightness",
            capability="display.set_brightness",
            manager="display",
            data={"level": 80},
        )

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_disp_mgr
            res = AuraToolRegistry._set_brightness(level=80)
            assert res["status"] == "success"
            assert res["message"] == "Display brightness set to 80%."
            mock_disp_mgr.execute.assert_called_once_with(
                "display.set_brightness", goal="set brightness", arguments={"level": 80}
            )

    def test_live_clipboard_roundtrip(self):
        """Live unmocked test of clipboard read and write."""
        write_res = AuraToolRegistry._handle_clipboard("write", "live test string 12345")
        assert write_res["status"] == "success"
        read_res = AuraToolRegistry._handle_clipboard("read")
        assert read_res["status"] == "success"
        assert read_res["content"] == "live test string 12345"

    def test_live_control_window_nonexistent_fails_safely(self):
        """Live unmocked test ensuring nonexistent window returns safe error."""
        res = AuraToolRegistry._control_window("definitely_nonexistent_window_aura_9999", "focus")
        assert res["status"] == "error"
        assert "No active window found matching" in res["message"]

    def test_control_window_close_nonexistent_fails_fast(self):
        """Test _control_window with close on nonexistent window fails fast without executing close."""
        mock_win_mgr = MagicMock()
        mock_win_mgr._find_window.return_value = None

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg:
            mock_reg.return_value.get_manager.return_value = mock_win_mgr
            res = AuraToolRegistry._control_window("GhostApp12345", "close")
            assert res["status"] == "error"
            assert "No active window found matching 'GhostApp12345'" in res["message"]
            mock_win_mgr.execute.assert_not_called()

    def test_set_volume_partial_failure_surfaced_accurately(self):
        """Test _set_volume reports error when volume fails even if mute succeeded in manager."""
        mock_audio_mgr = MagicMock()
        mock_audio_mgr.execute.side_effect = [
            DesktopResult.create_success(
                goal="toggle mute",
                capability="audio.toggle_mute",
                manager="audio",
                data={"muted": True},
            ),
            DesktopResult.create_failure(
                goal="set volume",
                capability="audio.set_volume",
                manager="audio",
                error="Device busy",
            ),
        ]

        with patch(
            "desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance"
        ) as mock_reg, patch(
            "pycaw.pycaw.AudioUtilities.GetSpeakers", side_effect=Exception("COM unavailable")
        ):
            mock_reg.return_value.get_manager.return_value = mock_audio_mgr
            res = AuraToolRegistry._set_volume(level=50, mute=True)
            assert res["status"] == "error"
            assert "Audio muted" in res["message"]
            assert "remaining adjustments failed" in res["message"]
