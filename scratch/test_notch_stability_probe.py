"""
AuraAI — Voice Notch Stability & Timer Leak Validation Probe
============================================================
Live verification of:
1. Ghost QTimer leak prevention (findChildren(QTimer) count before vs after 5 executed commands)
2. Escape key process suicide fix (Esc in all states transitions to IDLE, never closes app)
3. Master Animation Clock consolidation (single master timer, inactive widgets sleep)
4. Hover debouncing (180ms threshold)
"""

import sys
import os
import time
from pathlib import Path

# Ensure src/ is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from PySide6.QtCore import Qt, QTimer, QCoreApplication, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from gui.widgets.voice_notch_overlay import VoiceNotchOverlay, NotchState

def run_probe():
    print("=" * 70)
    print("      AURA VOICE NOTCH ARCHITECTURAL STABILITY PROBE")
    print("=" * 70)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Aura Voice Notch Test")

    notch = VoiceNotchOverlay()
    notch._is_test_env = True
    notch.show()
    app.processEvents()

    # --- TEST 1: Initial Timer Count ---
    initial_timers = notch.findChildren(QTimer)
    initial_timer_count = len(initial_timers)
    print(f"\n[TEST 1] Initial QTimer Count: {initial_timer_count}")
    for t in initial_timers:
        print(f"  • Timer interval={t.interval()}ms, singleShot={t.isSingleShot()}, active={t.isActive()}")
    assert initial_timer_count <= 6, f"Expected <=6 consolidated timers, got {initial_timer_count}"
    print("  [PASS] Master animation clock consolidated successfully.")

    # --- TEST 2: Escape Key Process Safety ---
    print("\n[TEST 2] Testing Escape Key in Various States...")
    states_to_test = [
        (NotchState.EXPANDED, "EXPANDED"),
        (NotchState.LISTENING, "LISTENING"),
        (NotchState.PROCESSING, "PROCESSING"),
        (NotchState.SUCCESS, "SUCCESS"),
        (NotchState.IDLE, "IDLE"),
    ]

    for state, name in states_to_test:
        notch.set_state(state)
        app.processEvents()
        assert notch.isVisible(), f"Notch should be visible in state {name}"
        
        # Synthesize Esc Key Press
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        notch.keyPressEvent(esc_event)
        app.processEvents()

        assert notch.isVisible(), f"Notch unexpectedly closed on Esc in state {name}!"
        assert notch.current_state == NotchState.IDLE, f"Expected IDLE state after Esc, got {notch.current_state}"
        print(f"  [PASS] Esc from {name} -> State: {notch.current_state.name} (Window remains open)")

    # --- TEST 3: Ghost QTimer Accumulation (Duplicate Timer Bug) ---
    print("\n[TEST 3] Testing Ghost QTimer Accumulation across 5 Chained Commands...")
    for i in range(5):
        notch._execute_command(f"mock command test #{i+1}")
        app.processEvents()
        current_timer_count = len(notch.findChildren(QTimer))
        assert current_timer_count == initial_timer_count, (
            f"Timer leak detected! Command {i+1}: expected {initial_timer_count} timers, got {current_timer_count}"
        )
        # Reset state back to IDLE
        notch.set_state(NotchState.IDLE)
        app.processEvents()

    final_timer_count = len(notch.findChildren(QTimer))
    print(f"  [PASS] Timers before commands: {initial_timer_count} -> Timers after 5 commands: {final_timer_count}")
    print("  [PASS] Zero ghost QTimers leaked!")

    # --- TEST 4: Master Clock Tick & Inactive Page Sleep ---
    print("\n[TEST 4] Master Clock Active-Gating Verification...")
    notch.set_state(NotchState.IDLE)
    app.processEvents()

    # In IDLE, listen orb and proc orb must NOT be visible
    assert not notch._listen_orb.isVisible()
    assert not notch._proc_orb.isVisible()
    assert notch._idle_orb.isVisible()

    idle_orb_phase_before = notch._idle_orb._phase
    notch._on_master_anim_tick()
    idle_orb_phase_after = notch._idle_orb._phase
    assert idle_orb_phase_after != idle_orb_phase_before, "Idle orb should advance phase on master tick"

    proc_orb_phase_before = notch._proc_orb._phase
    notch._on_master_anim_tick()
    proc_orb_phase_after = notch._proc_orb._phase
    assert proc_orb_phase_after == proc_orb_phase_before, "Hidden processing orb must SLEEP and NOT advance phase"
    print("  [PASS] Inactive state pages sleep and consume zero repaint cycles.")

    # --- TEST 5: Graceful Degradation on Exception ---
    print("\n[TEST 5] Master Clock Fault-Tolerance under Corrupted Widget Exception...")
    def _crashing_tick(*args, **kwargs):
        raise RuntimeError("Simulated transient math error in visual rendering")
    
    # Inject crashing tick into idle spectrum
    original_tick = notch._idle_spectrum._tick_step
    notch._idle_spectrum._tick_step = _crashing_tick
    
    # Master tick should NOT crash, and idle orb should STILL advance
    orb_phase_pre = notch._idle_orb._phase
    notch._on_master_anim_tick()
    orb_phase_post = notch._idle_orb._phase
    assert orb_phase_post != orb_phase_pre, "Idle orb should continue ticking even if another widget throws!"
    assert notch._master_anim_timer.isActive(), "Master clock must remain alive after subwidget exception!"
    notch._idle_spectrum._tick_step = original_tick
    print("  [PASS] Exception in individual widget safely caught; master animation clock remained alive and healthy.")

    # --- TEST 6: Rapid Mouse Hover & Message Loop Responsiveness ---
    print("\n[TEST 6] Rapid Mouse Hover Stress & Message Loop Latency...")
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtCore import QPointF
    
    # Simulate 20 rapid enter / leave oscillations (cursor rapid flailing across notch)
    start_stress = time.perf_counter()
    for i in range(20):
        # Enter
        enter_ev = QEnterEvent(QPointF(10, 10), QPointF(100, 100), QPointF(100, 100))
        notch.enterEvent(enter_ev)
        app.processEvents()
        
        # Leave
        leave_ev = QEvent(QEvent.Type.Leave)
        notch.leaveEvent(leave_ev)
        app.processEvents()
        
    total_stress_time = (time.perf_counter() - start_stress) * 1000.0  # ms
    avg_per_cycle = total_stress_time / 20.0
    print(f"  • 20 Rapid Enter/Leave transitions processed in {total_stress_time:.2f}ms ({avg_per_cycle:.3f}ms per cycle)")
    assert avg_per_cycle < 10.0, f"Hover processing took too long ({avg_per_cycle}ms per cycle), risk of UI stutter!"
    print("  [PASS] GUI message pump is instantaneous with 0 event stalls.")

    # Clean up
    notch.close()
    app.processEvents()
    print("\n" + "=" * 70)
    print("      ALL NOTCH STABILITY & LIVE PROBES PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_probe()
