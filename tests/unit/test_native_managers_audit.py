"""
Unit Tests for Track B: Native Managers Audit (ClipboardManager & DisplayManager).
Verifies rollback closures, verification structures, and Win32 error handling contracts.
"""

from unittest.mock import patch

from src.desktop.native.managers.clipboard_manager import ClipboardManager
from src.desktop.native.managers.display_manager import DisplayManager


def test_clipboard_manager_write_and_rollback():
    """Verify ClipboardManager.write_text captures prior text and attaches an active rollback closure."""
    mgr = ClipboardManager()

    # Seed initial text
    mgr._set_text_to_clipboard("Initial Clipboard Text")

    # Execute write_text
    res = mgr.execute("clipboard.write_text", "Copy greeting", {"text": "Hello World"})
    assert res.success is True
    assert res.data["text"] == "Hello World"
    assert res.data["previous_text"] == "Initial Clipboard Text"
    assert res.rollback is not None
    assert callable(res.rollback)

    # Verify clipboard now has new text
    assert mgr._get_text_from_clipboard() == "Hello World"

    # Execute rollback closure
    res.rollback()

    # Verify clipboard was restored to initial text
    assert mgr._get_text_from_clipboard() == "Initial Clipboard Text"


def test_clipboard_manager_clear_and_rollback():
    """Verify ClipboardManager.clear captures prior text and attaches an active rollback closure."""
    mgr = ClipboardManager()

    # Seed initial text
    mgr._set_text_to_clipboard("Text Before Clear")

    # Execute clear
    res = mgr.execute("clipboard.clear", "Clear clipboard", {})
    assert res.success is True
    assert res.data["cleared"] is True
    assert res.data["previous_text"] == "Text Before Clear"
    assert res.rollback is not None
    assert callable(res.rollback)

    # Execute rollback closure
    res.rollback()

    # Verify clipboard restored
    assert mgr._get_text_from_clipboard() == "Text Before Clear"


def test_clipboard_manager_read_files_parsing():
    """Verify ClipboardManager.read_files parses actual file paths from CF_HDROP."""
    mgr = ClipboardManager()

    with patch("win32clipboard.IsClipboardFormatAvailable", return_value=True), \
         patch.object(mgr, "_open_clipboard"), \
         patch("win32clipboard.GetClipboardData", return_value=("C:\\test1.txt", "C:\\test2.txt")), \
         patch("win32clipboard.CloseClipboard"):

        res = mgr.execute("clipboard.read_files", "Read copied files", {})
        assert res.success is True
        assert res.data["files"] == ["C:\\test1.txt", "C:\\test2.txt"]
        assert res.data["count"] == 2


def test_display_manager_brightness_rollback_and_verification():
    """Verify DisplayManager.set_brightness attaches rollback closure and verification dictionary."""
    mgr = DisplayManager()

    mock_prev = {"level": 70, "supported": True, "method": "wmi"}
    mock_curr = {"level": 90, "supported": True, "method": "wmi"}

    with patch("src.desktop.native.managers.display_helpers.get_display_brightness", side_effect=[mock_prev, mock_curr]), \
         patch("src.desktop.native.managers.display_helpers.set_display_brightness", return_value={"success": True, "level": 90, "method": "wmi"}) as mock_set:

        res = mgr.execute("display.set_brightness", "Set brightness to 90", {"level": 90})
        assert res.success is True
        assert res.data["level"] == 90
        assert res.data["previous_level"] == 70
        assert res.rollback is not None
        assert res.verification is not None
        assert res.verification["verified"] is True
        assert res.verification["current_level"] == 90

        # Test rollback execution
        res.rollback()
        mock_set.assert_called_with(70)


def test_display_manager_resolution_rollback_and_verification():
    """Verify DisplayManager.set_resolution attaches rollback closure and verification dictionary."""
    mgr = DisplayManager()

    mock_prev_settings = {"width": 1920, "height": 1080, "orientation": 0}
    mock_curr_settings = {"width": 2560, "height": 1440, "orientation": 0}

    with patch("src.desktop.native.managers.display_helpers.get_display_settings", side_effect=[mock_prev_settings, mock_curr_settings]), \
         patch("src.desktop.native.managers.display_helpers.set_display_resolution", return_value=True) as mock_set:

        res = mgr.execute("display.set_resolution", "Change resolution to 2560x1440", {"width": 2560, "height": 1440})
        assert res.success is True
        assert res.data["width"] == 2560
        assert res.data["height"] == 1440
        assert res.data["previous_width"] == 1920
        assert res.data["previous_height"] == 1080
        assert res.rollback is not None
        assert res.verification is not None
        assert res.verification["verified"] is True
        assert res.verification["current_width"] == 2560

        # Test rollback execution
        res.rollback()
        mock_set.assert_called_with("\\\\.\\DISPLAY1", 1920, 1080)


def test_display_manager_orientation_rollback_and_verification():
    """Verify DisplayManager.set_orientation attaches rollback closure and verification dictionary."""
    mgr = DisplayManager()

    mock_prev_settings = {"width": 1920, "height": 1080, "orientation": 0}
    mock_curr_settings = {"width": 1080, "height": 1920, "orientation": 1}

    with patch("src.desktop.native.managers.display_helpers.get_display_settings", side_effect=[mock_prev_settings, mock_curr_settings]), \
         patch("src.desktop.native.managers.display_helpers.set_display_orientation", return_value=True) as mock_set:

        res = mgr.execute("display.set_orientation", "Change orientation to portrait", {"orientation": 1})
        assert res.success is True
        assert res.data["orientation"] == 1
        assert res.data["previous_orientation"] == 0
        assert res.rollback is not None
        assert res.verification is not None
        assert res.verification["verified"] is True

        # Test rollback execution
        res.rollback()
        mock_set.assert_called_with("\\\\.\\DISPLAY1", 0)


def test_security_manager_defender_fallback_when_restricted():
    """Verify SecurityManager.firewall_audit fails gracefully when Defender query is restricted/third-party AV."""
    from src.desktop.native.managers.security_manager import SecurityManager
    mgr = SecurityManager()

    # Mock netsh succeeding but Defender query returning non-zero / error
    def mock_sandbox_exec(cmd: str):
        if "netsh advfirewall" in cmd:
            return (0, "Domain Profile Settings: State ON", "")
        elif "Get-MpComputerStatus" in cmd:
            return (1, "", "Access denied / service disabled")
        return (0, "", "")

    with patch.object(mgr._sandbox, "execute", side_effect=mock_sandbox_exec):
        res = mgr.execute("security.firewall_audit", "Audit host firewall and defender", {})
        assert res.success is True
        assert "Domain Profile Settings" in res.data["firewall_status"]
        assert "Unavailable" in res.data["antivirus_status"]
        assert len(res.warnings) > 0
        assert "Defender query returned code 1" in res.warnings[0]


def test_display_manager_unsupported_resolution_error_handling():
    """Verify DisplayManager.set_resolution returns failure when Win32 rejects mode."""
    mgr = DisplayManager()

    with patch("src.desktop.native.managers.display_helpers.get_display_settings", return_value={"width": 1920, "height": 1080}), \
         patch("src.desktop.native.managers.display_helpers.set_display_resolution", return_value=False):

        res = mgr.execute("display.set_resolution", "Change resolution to 9999x9999", {"width": 9999, "height": 9999})
        assert res.success is False
        assert "unsupported" in res.error.lower() or "failed" in res.error.lower()
        assert res.rollback is None

