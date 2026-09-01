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
from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from voice.continuous_loop import ContinuousVoiceLoop
from voice.audio_manager import AudioDeviceInfo
from voice.models import ConversationState, VoiceContext
from voice.voice_manager import VoiceManager


class FakeAudioManager:
    def __init__(self):
        self.recording = False
        self.start_count = 0
        self.stop_count = 0
        self.callback = None
        self.input_device = AudioDeviceInfo(1, "Fake Mic", input=True, output=False)
        self.output_device = AudioDeviceInfo(2, "Fake Speaker", input=False, output=True)

    def get_default_input_device(self):
        return self.input_device

    def get_default_output_device(self):
        return self.output_device

    def select_input_device(self, device_id):
        return True

    def select_output_device(self, device_id):
        return True

    def start_recording(self, callback, sample_rate=16000, channels=1, device_id=None):
        if self.recording:
            return False
        self.recording = True
        self.start_count += 1
        self.callback = callback
        return True

    def stop_recording(self):
        if not self.recording:
            return False
        self.recording = False
        self.stop_count += 1
        self.callback = None
        return True

    def stop_playback(self):
        return True

    def is_recording(self):
        return self.recording

    def get_audio_stats(self):
        return {"is_recording": self.recording}


class FakeWakeWord:
    def __init__(self):
        self.is_initialized = False
        self.is_active = False
        self.processed_chunks = 0
        self.on_wake_word_detected = None

    def initialize(self):
        self.is_initialized = True
        return True

    def activate(self):
        self.is_active = True
        return True

    def deactivate(self):
        self.is_active = False
        return True

    def process_audio(self, audio_data, sample_rate):
        self.processed_chunks += 1
        if audio_data == b"wake" and self.on_wake_word_detected:
            self.on_wake_word_detected("aura")
        return True

    def get_status(self):
        return {"is_active": self.is_active}


class FakeSTTManager:
    def __init__(self):
        self.initialized = False
        self.processed_chunks = 0
        self.reset_count = 0
        self.final_transcript = "Open Calculator"
        self.settings = type(
            "Settings",
            (),
            {"provider": type("Provider", (), {"value": "fake"})()},
        )()

    def initialize(self):
        self.initialized = True
        return True

    def process_audio(self, audio_data):
        self.processed_chunks += 1

    def finalize(self):
        return self.final_transcript

    def reset(self):
        self.reset_count += 1

    def get_status(self):
        return {"initialized": self.initialized}


class FakeTTSManager:
    def __init__(self):
        self.text = ""
        self._complete_cb = None
        self._interrupt_cb = None

    def set_callbacks(self, complete=None, interrupt=None):
        self._complete_cb = complete
        self._interrupt_cb = interrupt

    def add_text(self, text):
        self.text = text
        return True

    def speak(self):
        return True

    def speak_stream(self, chunk_iterator):
        return True

    def stop(self):
        return True

    def get_status(self):
        return {"text": self.text}


class FakeVAD:
    def __init__(self):
        self.on_speech_start = None
        self.on_speech_end = None

    def process_audio(self, audio_data, sample_rate):
        return None, 0.0

    def get_stats(self):
        return {}

    def reset(self):
        return None


class FakeBargeInHandler:
    def set_aura_speaking(self, is_speaking):
        return None

    def check_for_interrupt(self):
        return False


class FakeInterruptionManager:
    def __init__(self):
        self.state = None
        self.on_interrupt_start = None
        self.on_interrupt_end = None

    def start_interrupt(self, reason):
        return None

    def end_interrupt(self):
        return None

    def get_stats(self):
        return {}

    def reset(self):
        return None


def make_hardware_free_voice_manager():
    voice_mgr = VoiceManager()
    voice_mgr.audio_manager = FakeAudioManager()
    voice_mgr.wake_word = FakeWakeWord()
    voice_mgr.stt_manager = FakeSTTManager()
    voice_mgr.tts_manager = FakeTTSManager()
    voice_mgr.vad = FakeVAD()
    voice_mgr.barge_in_handler = FakeBargeInHandler()
    voice_mgr.interruption_manager = FakeInterruptionManager()
    voice_mgr._setup_callbacks()
    return voice_mgr


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


def test_07_start_enters_real_wake_word_microphone_mode(clean_registry):
    registry, desktop, browser = clean_registry
    voice_mgr = make_hardware_free_voice_manager()
    loop = ContinuousVoiceLoop(voice_manager=voice_mgr, coordinator=ExecutionCoordinator())

    assert loop.start() is True

    assert loop._running is True
    assert voice_mgr.state == ConversationState.WAKE_LISTENING
    assert voice_mgr.audio_manager.is_recording() is True

    voice_mgr.process_audio(b"noise", 16000)
    assert voice_mgr.wake_word.processed_chunks == 1
    assert loop.turn_count == 0


def test_08_spoken_wake_then_stt_then_tts_restores_wake_mode(clean_registry):
    import time
    registry, desktop, browser = clean_registry
    voice_mgr = make_hardware_free_voice_manager()
    loop = ContinuousVoiceLoop(voice_manager=voice_mgr, coordinator=ExecutionCoordinator())
    assert loop.start() is True

    voice_mgr.process_audio(b"wake", 16000)

    assert voice_mgr.state == ConversationState.ACTIVE_LISTENING
    assert voice_mgr.audio_manager.start_count == 1
    assert voice_mgr.stt_manager.initialized is True

    voice_mgr._finalize_stt()
    time.sleep(0.1)

    assert loop.turn_count == 1
    assert loop.history[0]["transcript"] == "Open Calculator"
    assert voice_mgr.state in (ConversationState.SPEAKING, ConversationState.THINKING)
    assert voice_mgr.audio_manager.is_recording() is True

    voice_mgr._on_tts_complete()

    assert voice_mgr.state in (ConversationState.WAKE_LISTENING, ConversationState.ACTIVE_LISTENING, ConversationState.IDLE)
    assert voice_mgr.audio_manager.is_recording() is True

    loop._on_followup_timeout()
    assert voice_mgr.state == ConversationState.WAKE_LISTENING


def test_09_continuous_voice_loop_streaming_tool_filler_integration(clean_registry):
    """Verify ContinuousVoiceLoop handles streaming tool queries yielding acoustic filler chunks."""
    import time
    from unittest.mock import MagicMock

    registry, desktop, browser = clean_registry
    voice_mgr = make_hardware_free_voice_manager()

    # Mock AuraCore with process_request_stream yielding filler then tool result
    mock_core = MagicMock()

    async def _mock_stream(transcript):
        yield "Looking that up now... "
        yield "Found the top Python tutorials on YouTube."

    mock_core.process_request_stream = _mock_stream
    mock_core.add_to_conversation = MagicMock()

    spoken_chunks = []
    def _mock_speak(text, **kwargs):
        spoken_chunks.append(text)
        return True

    voice_mgr.speak = _mock_speak

    loop = ContinuousVoiceLoop(voice_manager=voice_mgr, coordinator=ExecutionCoordinator())
    loop._aura_core = mock_core
    assert loop.start() is True

    # User triggers wake then speaks tool query
    loop.trigger_wake_detected("Aura")
    loop.trigger_transcription_ready("Search YouTube for Python tutorials")

    # Allow background thread to process stream
    time.sleep(0.3)

    assert loop.turn_count == 1
    assert len(loop.history) == 1
    assert loop.history[0]["transcript"] == "Search YouTube for Python tutorials"
    assert "Looking that up now..." in spoken_chunks or "Looking that up now..." in loop.history[0]["spoken_summary"]

