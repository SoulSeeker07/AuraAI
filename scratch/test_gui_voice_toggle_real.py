import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

# Set offscreen Qt platform so GUI window tests can run headlessly on any machine
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from core.aura_core import AuraCore
from gui.signals import app_signals

print("=" * 60)
print("REAL LIVE TEST: GUI MIC TOGGLE & CONTINUOUS VOICE BACKEND")
print("=" * 60)

app = QApplication.instance() or QApplication(sys.argv)

print("\n1. Initializing MainWindow...")
window = MainWindow()

print("\n2. Initial State Verification:")
print(f"  - _mic_active: {window._mic_active}")
print(f"  - _mic_btn checked: {window._mic_btn.isChecked()}")
print(f"  - Core State Label: {window._core_state_lbl.text()}")
print(f"  - Placeholder: {window._chat_input.placeholderText()}")

print("\n3. Simulating REAL User Click on Mic Toggle Button (Turning ON)...")
window._mic_btn.click()

print("\n4. State After Mic Toggle ON:")
print(f"  - _mic_active: {window._mic_active}")
print(f"  - _mic_btn checked: {window._mic_btn.isChecked()}")
print(f"  - Core State Label: {window._core_state_lbl.text()}")
print(f"  - Placeholder: {window._chat_input.placeholderText()}")
print(f"  - Last Command Dispatched: {getattr(window, '_last_command_text', None)}")

# Process events to allow CommandWorker thread to launch and process
app.processEvents()

print("\n5. Simulating REAL User Click on Mic Toggle Button (Turning OFF)...")
window._mic_btn.click()

print("\n6. State After Mic Toggle OFF:")
print(f"  - _mic_active: {window._mic_active}")
print(f"  - _mic_btn checked: {window._mic_btn.isChecked()}")
print(f"  - Core State Label: {window._core_state_lbl.text()}")
print(f"  - Placeholder: {window._chat_input.placeholderText()}")
print(f"  - Last Command Dispatched: {getattr(window, '_last_command_text', None)}")

print("\n7. Testing External Voice Signal Sync (e.g. from CLI or spoken 'start listening'):")
app_signals.voice_status_changed.emit(True)
app.processEvents()
print(f"  - Triggered voice_status_changed(True)")
print(f"  - _mic_active in GUI: {window._mic_active}")
print(f"  - _mic_btn checked in GUI: {window._mic_btn.isChecked()}")
print(f"  - Core State Label: {window._core_state_lbl.text()}")

app_signals.voice_status_changed.emit(False)
app.processEvents()
print(f"  - Triggered voice_status_changed(False)")
print(f"  - _mic_active in GUI: {window._mic_active}")
print(f"  - _mic_btn checked in GUI: {window._mic_btn.isChecked()}")
print(f"  - Core State Label: {window._core_state_lbl.text()}")

print("\n" + "=" * 60)
print("ALL LIVE TESTS COMPLETED WITH REAL GUI & BACKEND INSTANCES")
print("=" * 60)
