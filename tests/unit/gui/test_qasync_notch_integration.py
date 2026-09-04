"""
Unit tests for qasync and Async Event Loop Integration with VoiceNotchOverlay
===========================================================================
Verifies:
1. When an active asyncio loop is running (e.g. qasync), _execute_command
   dispatches via asyncio.create_task and _process_command_async.
2. The async coroutine queries AuraCore asynchronously and emits message_received.
3. Fallback path executes via threading.Thread when no loop is active.
"""

import asyncio
import os
import sys
import threading
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import qasync
from PySide6.QtWidgets import QApplication
from gui.widgets.voice_notch_overlay import VoiceNotchOverlay
from gui.signals import app_signals


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.mark.asyncio
async def test_notch_qasync_command_execution(qapp):
    """Verify that inside an active asyncio loop, commands are executed asynchronously."""
    overlay = VoiceNotchOverlay()
    received_msgs = []

    def on_msg(sender, content, is_user):
        received_msgs.append((sender, content, is_user))

    app_signals.message_received.connect(on_msg)

    try:
        mock_core = MagicMock()
        mock_core.get_ai_response = AsyncMock(return_value="Command successfully handled via qasync.")

        with patch("core.aura_core.AuraCore.get_instance", return_value=mock_core), \
             patch("core.aura_core.AuraCore._instance", mock_core):
            overlay._execute_command("hello aura")

            # Yield control so asyncio.create_task coroutine runs
            await asyncio.sleep(0.1)
            qapp.processEvents()

            assert len(received_msgs) >= 1
            sender, text, is_user = received_msgs[-1]
            assert sender == "AuraAI"
            assert "Command successfully handled via qasync." in text
    finally:
        app_signals.message_received.disconnect(on_msg)
        overlay.close()


def test_notch_thread_fallback_command_execution(qapp):
    """Verify fallback to threading.Thread when no event loop is running."""
    overlay = VoiceNotchOverlay()
    received_msgs = []
    done_event = threading.Event()

    def on_msg(sender, content, is_user):
        received_msgs.append((sender, content, is_user))
        done_event.set()

    app_signals.message_received.connect(on_msg)

    try:
        mock_core = MagicMock()
        async def fake_response(query, enable_tools=True):
            return "Fallback thread execution success."
        mock_core.get_ai_response = fake_response

        # Force asyncio.get_running_loop to raise RuntimeError to test fallback
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("No running loop")), \
             patch("core.aura_core.AuraCore.get_instance", return_value=mock_core), \
             patch("core.aura_core.AuraCore._instance", mock_core):
            overlay._execute_command("run fallback")

            # Pump Qt events while waiting for the cross-thread signal to be processed
            import time
            start = time.time()
            while not done_event.is_set() and time.time() - start < 5.0:
                qapp.processEvents()
                time.sleep(0.02)
            qapp.processEvents()

            assert done_event.is_set() is True
            assert len(received_msgs) >= 1
            assert "Fallback thread execution success." in received_msgs[-1][1]
    finally:
        app_signals.message_received.disconnect(on_msg)
        overlay.close()
