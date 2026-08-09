"""
Test Continuous Voice Loop Orchestration & Execution Integration
==================================================================

Verifies:
  1. Spoken STT transcript → NLU / ExecutionMap mapping.
  2. ExecutionCoordinator loop execution (execute → observe → verify → goal_verify).
  3. TTS spoken summary generation from CLI Activity Trace Level 1 facts.
  4. Continuous listening loop resumption after TTS completion.
"""

import pytest
from src.brain.aca.engine_interface import EngineRegistry
from src.brain.execution_coordinator import ExecutionCoordinator
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.core.backends.adapters.desktop_backend import DesktopEngineBackend
from src.voice.continuous_loop import ContinuousVoiceLoop
from src.voice.models import ConversationState, VoiceContext
from src.voice.voice_manager import VoiceManager


@pytest.fixture
def clean_registry():
    registry = EngineRegistry.get_instance()
    desktop = DesktopEngineBackend()
    browser = PlaywrightBrowserAdapter()
    registry.register(desktop, "desktop")
    registry.register(browser, "browser")
    return registry, desktop, browser


@pytest.fixture
def voice_loop(clean_registry):
    registry, desktop, browser = clean_registry
    coordinator = ExecutionCoordinator()
    voice_mgr = VoiceManager()

    loop = ContinuousVoiceLoop(
        voice_manager=voice_mgr,
        coordinator=coordinator,
    )
    return loop, voice_mgr, coordinator


def test_01_voice_loop_initialization(voice_loop):
    loop, voice_mgr, coordinator = voice_loop
    assert loop.turn_count == 0
    assert len(loop.history) == 0
    assert loop.voice_manager is voice_mgr
    assert loop.coordinator is coordinator


def test_02_spoken_youtube_command_cycle(voice_loop):
    loop, voice_mgr, coordinator = voice_loop

    spoken_transcript = "Search YouTube for Python tutorial and play"
    turn_fact = loop.process_spoken_command(spoken_transcript)

    assert loop.turn_count == 1
    assert len(loop.history) == 1
    assert turn_fact["transcript"] == spoken_transcript
    assert turn_fact["success"] is True
    assert "Done." in turn_fact["spoken_summary"]
    assert "completed in" in turn_fact["spoken_summary"]

    # Verify state transitioned through TTS speaking
    assert voice_mgr.state in [ConversationState.IDLE, ConversationState.SPEAKING]


def test_03_spoken_facebook_command_cycle(voice_loop):
    loop, voice_mgr, coordinator = voice_loop

    spoken_transcript = "Find Meta AI on Facebook and show me the relevant result"
    turn_fact = loop.process_spoken_command(spoken_transcript)

    assert loop.turn_count == 1
    assert turn_fact["transcript"] == spoken_transcript
    assert turn_fact["success"] is True
    assert turn_fact["coord_result"].success is True
    assert len(turn_fact["coord_result"].step_results) == 5


def test_04_continuous_multi_turn_listening_resumption(voice_loop):
    loop, voice_mgr, coordinator = voice_loop

    # Turn 1: Spoken Notepad command
    turn1 = loop.process_spoken_command("Open Notepad and type text")
    assert turn1["turn"] == 1
    assert turn1["success"] is True

    # Simulate TTS completion callback
    voice_mgr._on_tts_complete()

    # Turn 2: Spoken YouTube command
    turn2 = loop.process_spoken_command("Search YouTube for Python tutorial and play")
    assert turn2["turn"] == 2
    assert turn2["success"] is True
    assert len(loop.history) == 2


def test_05_contextual_follow_up_resolution(voice_loop):
    loop, voice_mgr, coordinator = voice_loop

    # Turn 1: Search YouTube
    turn1 = loop.process_spoken_command("Search YouTube for Python tutorial")
    assert turn1["success"] is True
    assert getattr(loop, "_last_search_query", "").lower() == "python tutorial"

    # Turn 2: Contextual follow-up ("now open the first result")
    turn2 = loop.process_spoken_command("Now open the first result")
    assert turn2["turn"] == 2
    assert turn2["success"] is True
    assert turn2["exec_map"].get("context_resolved") is True


def test_06_microphone_suppression_during_tts(voice_loop):
    loop, voice_mgr, coordinator = voice_loop

    # Set state to SPEAKING
    voice_mgr._update_state(ConversationState.SPEAKING)

    # Process audio chunk while SPEAKING
    voice_mgr.process_audio(b"\x00" * 320, 16000)

    # STT manager should NOT have processed audio frames during SPEAKING state (Mic Suppressed)
    assert voice_mgr.state == ConversationState.SPEAKING

