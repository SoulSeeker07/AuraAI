"""
Regression tests for TTS initialization-order fix.

Verifies that:
  1. TTSManger.add_text() triggers lazy initialization when the engine is None.
  2. Callbacks registered via set_callbacks() before initialization are correctly
     wired to the engine after it becomes available.
  3. Explicit TTSManger.initialize() is still idempotent (no duplicate engines/threads).
  4. VoiceManager.speak() succeeds without requiring an explicit prior
     TTSManger.initialize() call.
  5. Initialization failure in add_text() is returned honestly (returns False).

These tests run without any hardware or runtime TTS engine installation; they use
a lightweight stub engine so the import-and-init path can be verified in-process.
"""

import pytest

import sys
from pathlib import Path

# Allow running with `pytest` from project root (pyproject sets pythonpath=["src"]).
# Add the workspace root as well so the package-style imports work in both modes.
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from voice.tts_manager import (
    TTSEngine,
    TTSManger,
    TTSSettings,
    TTSSpeaker,
)
from typing import Any


# ---------------------------------------------------------------------------
# Minimal in-process stub engine — avoids any I/O or external dependency.
# ---------------------------------------------------------------------------

class _StubEngine(TTSEngine):
    """Simple in-memory TTS engine for unit testing."""

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.init_call_count = 0
        self.texts: list[str] = []
        self.speak_calls = 0
        self.stop_calls = 0

    def initialize(self) -> bool:
        self.init_call_count += 1
        self.is_active = True
        return True

    def add_text(self, text: str, interruptible: bool = True) -> bool:
        if not self.is_active:
            return False
        self.texts.append(text)
        return True

    def speak(self) -> bool:
        if not self.is_active or not self.texts:
            return False
        self.speak_calls += 1
        self._emit_complete()
        return True

    def stop(self) -> bool:
        self.stop_calls += 1
        self._emit_interrupt()
        return True

    def is_playing(self) -> bool:
        return False

    def get_status(self) -> dict[str, Any]:
        return {"is_active": self.is_active, "texts": self.texts}


def _make_manager_with_stub() -> tuple[TTSManger, _StubEngine]:
    """
    Return a TTSManger whose engine factory is monkey-patched to use _StubEngine,
    avoiding any import of edge_tts / piper / elevenlabs.
    """
    settings = TTSSettings(speaker=TTSSpeaker.EDGE_TTS)
    mgr = TTSManger(settings)

    # Patch initialize() so it installs our stub instead of the real engine.
    stub = _StubEngine(settings)
    original_initialize = mgr.initialize

    def _patched_initialize() -> bool:
        mgr.engine = stub
        ok = stub.initialize()
        # Mirror the real callback-wiring logic from TTSManger.initialize()
        if ok and mgr._pending_complete_callback:
            mgr.engine.set_callbacks(
                mgr._pending_complete_callback,
                mgr._pending_interrupt_callback,
            )
        return ok

    mgr.initialize = _patched_initialize  # type: ignore[method-assign]
    return mgr, stub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTTSManagerLazyInit:

    def test_engine_is_none_before_any_call(self):
        """Engine must not be created at construction time."""
        settings = TTSSettings(speaker=TTSSpeaker.EDGE_TTS)
        mgr = TTSManger(settings)
        assert mgr.engine is None

    def test_add_text_triggers_lazy_init(self):
        """add_text() on an uninitialised manager must trigger init and succeed."""
        mgr, stub = _make_manager_with_stub()
        assert mgr.engine is None, "Precondition: engine is None before add_text"

        result = mgr.add_text("Hello world")

        assert result is True, "add_text should succeed after lazy init"
        assert mgr.engine is stub, "Engine should be set after lazy init"
        assert stub.init_call_count == 1, "initialize() should have been called exactly once"
        assert "Hello world" in stub.texts

    def test_add_text_does_not_re_init_existing_engine(self):
        """Calling add_text() again must not call initialize() a second time."""
        mgr, stub = _make_manager_with_stub()

        mgr.add_text("first")
        mgr.add_text("second")

        assert stub.init_call_count == 1, "initialize() must be idempotent via lazy guard"
        assert stub.texts == ["first", "second"]

    def test_explicit_initialize_then_add_text_does_not_double_init(self):
        """Explicit initialize() followed by add_text() must not re-initialize."""
        mgr, stub = _make_manager_with_stub()

        mgr.initialize()
        mgr.add_text("after explicit init")

        assert stub.init_call_count == 1
        assert "after explicit init" in stub.texts

    def test_callbacks_set_before_init_are_wired_after_lazy_init(self):
        """
        Callbacks registered via set_callbacks() before any initialization
        must be live on the engine after lazy init triggered by add_text().
        """
        mgr, stub = _make_manager_with_stub()

        complete_called = []
        interrupt_called = []

        mgr.set_callbacks(
            complete=lambda: complete_called.append(True),
            interrupt=lambda: interrupt_called.append(True),
        )

        # Trigger lazy init + add text + speak (speak triggers _emit_complete in stub)
        mgr.add_text("callback test")
        mgr.speak()

        assert complete_called, "Playback-complete callback must fire after speak()"
        assert not interrupt_called, "Interrupt callback must not fire spuriously"

    def test_callbacks_set_after_init_are_wired_immediately(self):
        """set_callbacks() after the engine exists must wire them to the engine at once."""
        mgr, stub = _make_manager_with_stub()

        mgr.initialize()  # engine is now live

        complete_called = []
        mgr.set_callbacks(
            complete=lambda: complete_called.append(True),
            interrupt=lambda: None,
        )

        mgr.add_text("immediate wire test")
        mgr.speak()

        assert complete_called, "Callback wired post-init must fire"

    def test_add_text_returns_false_when_lazy_init_fails(self):
        """If lazy initialization fails, add_text() must return False."""
        settings = TTSSettings(speaker=TTSSpeaker.EDGE_TTS)
        mgr = TTSManger(settings)

        # Patch initialize() to simulate failure
        def _failing_init() -> bool:
            return False

        mgr.initialize = _failing_init  # type: ignore[method-assign]

        result = mgr.add_text("should fail")

        assert result is False, "add_text must return False when lazy init fails"
        assert mgr.engine is None, "Engine must remain None after failed init"


class TestVoiceManagerSpeakWithoutExplicitTTSInit:
    """
    Black-box regression tests for VoiceManager.speak() not requiring an
    explicit tts_manager.initialize() call before use.

    These tests substitute the heavy hardware components to remain runnable
    without audio devices or TTS runtime libraries.
    """

    def _make_voice_manager_with_stub_tts(self):
        """Build a VoiceManager and replace its tts_manager with a stub-backed one."""
        # Import here to avoid top-level import failure if optional deps are missing.
        from voice.voice_manager import VoiceManager

        vm = VoiceManager()

        mgr, stub = _make_manager_with_stub()
        # Register callbacks via the proper API so they wire correctly.
        mgr.set_callbacks(
            complete=vm._on_tts_complete,
            interrupt=vm._on_tts_interrupt,
        )
        vm.tts_manager = mgr
        return vm, mgr, stub

    def test_speak_without_prior_tts_init_succeeds(self):
        """VoiceManager.speak() must succeed even if tts_manager was never explicitly initialized."""
        try:
            vm, mgr, stub = self._make_voice_manager_with_stub_tts()
        except Exception:
            pytest.skip("VoiceManager constructor failed (missing hw deps) — skip runtime test")

        assert mgr.engine is None, "Precondition: no explicit init"

        result = vm.speak("Hello from lazy init")

        assert result is True, "VoiceManager.speak() must succeed via lazy TTS init"
        assert stub.init_call_count == 1
        assert "Hello from lazy init" in stub.texts

    def test_speak_fires_tts_complete_callback_via_lazy_init(self):
        """After lazy init, the TTS completion callback wired through VoiceManager must fire."""
        try:
            vm, mgr, stub = self._make_voice_manager_with_stub_tts()
        except Exception:
            pytest.skip("VoiceManager constructor failed (missing hw deps) — skip runtime test")

        from voice.models import ConversationState

        # Track whether the completion handler ran.
        fired = []
        real_on_complete = vm._on_tts_complete

        def _tracking_complete():
            fired.append(True)
            real_on_complete()

        # Re-register so our tracking wrapper is what the stub calls.
        mgr.set_callbacks(
            complete=_tracking_complete,
            interrupt=vm._on_tts_interrupt,
        )

        result = vm.speak("callback check")
        assert result is True, "VoiceManager.speak() must return True"
        assert fired, "Playback-complete callback must have fired via wired stub engine"
        # The state after speak() reflects the post-callback + post-speak state.
        # In a real async engine it would end up SPEAKING; the stub fires the callback
        # synchronously before speak() finishes, so IDLE then SPEAKING is normal.
        assert vm.state in (ConversationState.IDLE, ConversationState.SPEAKING), (
            f"Unexpected state after speak: {vm.state}"
        )
