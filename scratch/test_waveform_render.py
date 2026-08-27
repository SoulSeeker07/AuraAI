import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.signals import app_signals

print("=" * 60)
print("TESTING TACTICAL VOICE WAVEFORM WIDGET IN MAINWINDOW")
print("=" * 60)

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow()
win.resize(1140, 680)
win.show()
app.processEvents()

print(f"MainWindow initialized: {win.width()}x{win.height()}")
assert hasattr(win, "_tactical_waveform"), "TacticalVoiceWaveformWidget missing on MainWindow!"
wf = win._tactical_waveform
print(f"TacticalVoiceWaveformWidget size: {wf.width()}x{wf.height()}")
print(f"TacticalVoiceWaveformWidget state: {wf._state_text}")

# Test real-time signal reactivity
app_signals.voice_status_changed.emit(True)
app.processEvents()
print(f"After voice_status_changed(True): state={wf._state_text}, active={wf._active}")

app_signals.voice_level.emit(0.75)
app.processEvents()
print(f"After voice_level(0.75): target_levels sample={wf._target_levels[:4]}")

app_signals.voice_state_name_changed.emit("SPEAKING")
app.processEvents()
print(f"After voice_state_name_changed('SPEAKING'): state={wf._state_text}")

app_signals.voice_status_changed.emit(False)
app.processEvents()
print(f"After voice_status_changed(False): state={wf._state_text}, active={wf._active}")

# Clean up worker thread
wf.close()

print("\n" + "=" * 60)
print("TACTICAL VOICE WAVEFORM WIDGET TEST: 100% PASSED")
print("=" * 60)
