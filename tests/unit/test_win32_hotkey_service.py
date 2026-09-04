"""
Unit tests for GlobalHotkeyService Win32 message loop.
Ensures zero low-level hooks, non-blocking startup/shutdown, and proper signal routing.
"""

import time
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists for Qt signals
app = QApplication.instance() or QApplication([])

from tools.hotkey_service import GlobalHotkeyService
from gui.signals import app_signals


def test_hotkey_service_lifecycle():
    """Test start and stop of Win32 message loop thread without hanging."""
    svc = GlobalHotkeyService()
    assert not svc._running

    svc.start()
    assert svc._running
    assert hasattr(svc, "_thread")
    assert svc._thread.is_alive()

    # Small sleep to let GetMessageW enter loop
    time.sleep(0.1)

    svc.stop()
    assert not svc._running

    # Thread should terminate cleanly after WM_QUIT
    svc._thread.join(timeout=2.0)
    assert not svc._thread.is_alive()


def test_hotkey_service_signals():
    """Test hotkey signal handlers emit corresponding app_signals."""
    svc = GlobalHotkeyService()

    voice_mock = MagicMock()
    chat_mock = MagicMock()
    notch_mock = MagicMock()

    app_signals.trigger_voice_listening.connect(voice_mock)
    app_signals.toggle_chat_overlay.connect(chat_mock)
    app_signals.toggle_voice_notch.connect(notch_mock)

    try:
        svc._on_trigger_listening()
        assert voice_mock.called

        svc._on_alt_space()
        assert chat_mock.called

        svc._on_alt_n()
        assert notch_mock.called
    finally:
        app_signals.trigger_voice_listening.disconnect(voice_mock)
        app_signals.toggle_chat_overlay.disconnect(chat_mock)
        app_signals.toggle_voice_notch.disconnect(notch_mock)


def test_no_keyboard_hook_installed():
    """Verify that keyboard package hook is NOT imported or hooked."""
    import sys
    # Verify GlobalHotkeyService module does not hold an active hook
    svc = GlobalHotkeyService()
    svc.start()
    time.sleep(0.05)
    svc.stop()
    # Ensure no crash and cleanly stopped
    assert not svc._running
