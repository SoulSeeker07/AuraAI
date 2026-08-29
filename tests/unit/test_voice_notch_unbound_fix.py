import sys
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists
app = QApplication.instance() or QApplication([])

from gui.widgets.voice_notch_overlay import VoiceNotchOverlay

def test_voice_notch_overlay_execute_command_no_unbound_error():
    notch = VoiceNotchOverlay()
    
    with patch("threading.Thread") as mock_thread:
        notch._execute_command("list focus threads")
        assert hasattr(notch, "_active_cmd_cancel_event")
        assert notch._active_cmd_cancel_event is not None
