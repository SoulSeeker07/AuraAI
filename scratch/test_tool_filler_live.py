"""
Live Verification: Tool-Triggered Filler Utterance Latency via ContinuousVoiceLoop
Location: scratch/test_tool_filler_live.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from core.aura_core import AuraCore
from brain.execution_coordinator import ExecutionCoordinator
from voice.continuous_loop import ContinuousVoiceLoop
from voice.voice_manager import VoiceManager
from voice.tts_manager import TTSSettings, TTSSpeaker


def test_live_voice_loop_tool_filler():
    print("=" * 85)
    print("  Live OS Test: Tool Filler Utterance via ContinuousVoiceLoop")
    print("=" * 85)

    aura = AuraCore()

    # Create VoiceManager with Piper TTS
    settings = TTSSettings(speaker=TTSSpeaker.PIPER)
    voice_mgr = VoiceManager()
    voice_mgr.tts_manager.settings = settings
    voice_mgr.tts_manager.initialize()

    coordinator = ExecutionCoordinator()
    loop = ContinuousVoiceLoop(voice_manager=voice_mgr, coordinator=coordinator)
    loop._aura_core = aura

    assert loop.start() is True

    tool_goal = "Search YouTube for Python tutorial"
    print(f"\nUser Goal (Tool Query): '{tool_goal}'")

    t0 = time.perf_counter()
    loop.trigger_transcription_ready(tool_goal)

    # Wait for turn processing to complete
    max_wait = 10.0
    start_wait = time.perf_counter()
    while time.perf_counter() - start_wait < max_wait:
        if len(loop.history) > 0 and loop.history[0].get("spoken_summary"):
            break
        time.sleep(0.05)

    t_end = time.perf_counter()

    turn = loop.history[0] if loop.history else {}
    telemetry = loop._turn_telemetry

    t5 = telemetry.get("T5_reasoning_start", 0)
    t6 = telemetry.get("T6_first_audio", 0)
    ttfa_ms = ((t6 - t5) * 1000) if (t5 and t6) else ((t_end - t0) * 1000)

    print("\n" + "-" * 85)
    print(f"Transcript Processed   : '{turn.get('transcript', '')}'")
    print(f"Spoken Summary (Full)  : '{turn.get('spoken_summary', '')}'")
    print(f"Telemetry TTFA         : {ttfa_ms:.1f} ms")
    print(f"Total Turn Time        : {(t_end - t0)*1000:.1f} ms")
    print(f"Acoustic Dead Air Eliminated : {'YES ✓' if ttfa_ms < 500 else 'NO ✗'}")
    print("-" * 85)

    loop.stop()
    return 0 if "Looking that up now" in turn.get("spoken_summary", "") else 1


if __name__ == "__main__":
    sys.exit(test_live_voice_loop_tool_filler())
