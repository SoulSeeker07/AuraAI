"""
GUI Test Suite Configuration & Hardware Mocking
Location: tests/unit/gui/conftest.py

Directory-scoped autouse fixtures for GUI unit tests:
1. Suppress live hardware / driver polling (pyaudio, psutil network/gpu subprocesses).
2. Cleanly stop and join any spawned QThread workers (TelemetryWorker, LiveAudioCaptureWorker, etc.)
   and close all top-level Qt widgets at test teardown.
"""

import sys
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread


@pytest.fixture(autouse=True)
def suppress_hardware_polling(monkeypatch):
    """
    Mock audio capture and system sampling hardware calls so GUI tests
    never touch physical microphone streams or native C-extension polling.
    """
    # 1. Mock PyAudio module-level
    mock_pyaudio_class = MagicMock()
    mock_pyaudio_inst = MagicMock()
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"\x00" * 1024
    mock_pyaudio_inst.open.return_value = mock_stream
    mock_pyaudio_class.return_value = mock_pyaudio_inst

    try:
        import pyaudio
        monkeypatch.setattr(pyaudio, "PyAudio", mock_pyaudio_class)
    except (ImportError, Exception):
        pass

    # 2. Mock psutil network/disk and worker sub-processes
    try:
        import psutil
        mock_net_io = MagicMock(bytes_sent=1000, bytes_recv=2000)
        mock_disk_io = MagicMock(read_bytes=1000, write_bytes=2000)
        monkeypatch.setattr(psutil, "net_io_counters", lambda *a, **kw: mock_net_io)
        monkeypatch.setattr(psutil, "disk_io_counters", lambda *a, **kw: mock_disk_io)
    except (ImportError, Exception):
        pass

    try:
        from gui.widgets.system_monitor_overlay import TelemetryWorker
        monkeypatch.setattr(TelemetryWorker, "_sample_gpus", lambda self: [])
        monkeypatch.setattr(TelemetryWorker, "_sample_wifi", lambda self: {
            "connected": True,
            "ssid": "TEST_NET",
            "signal_pct": 100,
            "band": "5 GHz",
            "state": "CONNECTED",
        })
    except (ImportError, Exception):
        pass

    yield


@pytest.fixture(autouse=True)
def stop_gui_threads_and_widgets():
    """
    Ensure every QThread worker and top-level widget created during a GUI test
    is properly stopped, joined, and closed before the next test begins.
    """
    yield

    app = QApplication.instance()
    if app is None:
        return

    # 1. Stop all workers across all top-level widgets created in the test
    for widget in list(app.topLevelWidgets()):
        try:
            # Check findChildren for any child QThread instances
            for thread in widget.findChildren(QThread):
                if thread.isRunning():
                    if hasattr(thread, "stop"):
                        thread.stop()
                    else:
                        thread.terminate()
                    thread.wait(500)

            # Also check direct instance attributes on the widget
            for attr_name in dir(widget):
                if attr_name.startswith("_") and not attr_name.startswith("__"):
                    try:
                        val = getattr(widget, attr_name, None)
                        if isinstance(val, QThread) and val.isRunning():
                            if hasattr(val, "stop"):
                                val.stop()
                            else:
                                val.terminate()
                            val.wait(500)
                    except Exception:
                        pass

            widget.close()
            widget.deleteLater()
        except Exception:
            pass

    # Process deferred deletion events
    app.processEvents()

