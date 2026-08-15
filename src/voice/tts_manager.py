"""
Text-to-Speech Manager

Streaming Text-to-Speech with low-latency, real-time playback.
Enables responsive voice interactions.

Primary TTS engine : Piper (local / offline)
Fallback TTS engine: Edge-TTS (online / Microsoft)
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project root — used to resolve relative model paths from .env / config.
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


def _resolve_model_path(raw: str | None) -> str | None:
    """Return an absolute path string, resolving relative paths from project root."""
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    resolved = _PROJECT_ROOT / p
    return str(resolved)


class TTSSpeaker(Enum):
    """Text-to-Speech speakers."""

    PIPER    = "piper"     # Piper TTS (local / primary)
    EDGE_TTS = "edge_tts"  # Microsoft Edge TTS (online / fallback)
    AZURE_TTS   = "azure_tts"
    GOOGLE_TTS  = "google_tts"
    LOCALLY     = "locally"


class TTSSettings:
    """Configuration for TTS."""

    def __init__(
        self,
        speaker: "TTSSpeaker | str" = TTSSpeaker.PIPER,
        voice: str | None = None,
        rate: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        streaming: bool = True,
        interruptible: bool = True,
        fallback_speaker: "TTSSpeaker | str | None" = None,
    ):
        # Coerce string to TTSSpeaker enum
        if isinstance(speaker, str):
            speaker_enum = None
            for member in TTSSpeaker:
                if member.value == speaker:
                    speaker_enum = member
                    break
            if speaker_enum is None:
                raise ValueError(f"Invalid speaker string: {speaker!r}")
            self.speaker = speaker_enum
        else:
            self.speaker = speaker

        # Coerce fallback_speaker string to TTSSpeaker enum if provided
        if isinstance(fallback_speaker, str):
            fallback_enum = None
            for member in TTSSpeaker:
                if member.value == fallback_speaker:
                    fallback_enum = member
                    break
            if fallback_enum is None:
                raise ValueError(f"Invalid fallback_speaker string: {fallback_speaker!r}")
            self.fallback_speaker = fallback_enum
        else:
            self.fallback_speaker = fallback_speaker

        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.streaming = streaming
        self.interruptible = interruptible

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker.value,
            "voice": self.voice,
            "rate": self.rate,
            "pitch": self.pitch,
            "volume": self.volume,
            "streaming": self.streaming,
            "interruptible": self.interruptible,
            "fallback_speaker": (
                self.fallback_speaker.value if self.fallback_speaker else None
            ),
        }


class TTSEngine(ABC):
    """Abstract TTS engine."""

    def __init__(self, settings: TTSSettings):
        self.settings = settings
        self.is_active = False
        self._is_playing = False
        self._stream: list[str] = []
        self._playback_complete_callback: Callable[[], None] | None = None
        self._interrupt_callback: Callable[[], None] | None = None

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def add_text(self, text: str, interruptible: bool = True) -> bool:
        """Add text to speech queue."""
        pass

    @abstractmethod
    def speak(self) -> bool:
        """Start speaking the queued text."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop current speech."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Check if currently speaking."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        pass

    def set_callbacks(
        self, complete: Callable[[], None], interrupt: Callable[[], None]
    ) -> None:
        self._playback_complete_callback = complete
        self._interrupt_callback = interrupt

    def _emit_complete(self) -> None:
        if self._playback_complete_callback:
            self._playback_complete_callback()

    def _emit_interrupt(self) -> None:
        if self._interrupt_callback:
            self._interrupt_callback()


import queue

class ChunkedStreamPlayer:
    """Thread-safe, persistent streaming audio player for real-time TTS.

    Invariants:
      1. Persistent RawOutputStream idling with silence between utterances to avoid
         device-opening latency penalties and audio clicks.
      2. Single-thread buffer ownership: the PortAudio callback thread is the ONLY
         thread that reads/modifies `_residual_bytes`.
      3. Non-blocking callback: `_queue.get_nowait()` with zero-padded silence fallback.
      4. `_abort_requested` flag set by `abort()` and cleared at the start of a new utterance
         via `start_utterance()`, preventing stale interruptions from aborting new speech.
      5. Off-audio-thread callback dispatching for `on_complete` and `on_interrupt`.
    """

    def __init__(self, sample_rate: int = 22050, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._stream: Any = None
        self._is_playing = False
        self._abort_requested = False
        self._sentinel_received = False
        self._residual_bytes = bytearray()
        self._on_complete: Callable[[], None] | None = None
        self._on_interrupt: Callable[[], None] | None = None
        self._lock = threading.Lock()

    def set_callbacks(
        self, complete: Callable[[], None] | None, interrupt: Callable[[], None] | None
    ) -> None:
        self._on_complete = complete
        self._on_interrupt = interrupt

    def _ensure_stream(self) -> bool:
        if self._stream is not None and self._stream.active:
            return True
        try:
            import sounddevice as sd

            self._stream = sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
            return True
        except Exception as e:
            logger.error(f"[ChunkedStreamPlayer] Failed to start RawOutputStream: {e}")
            return False

    def _audio_callback(self, outdata: memoryview, frames: int, time_info: Any, status: Any) -> None:
        bytes_needed = frames * 2 * self.channels

        # Single-threaded abort processing on audio thread
        if self._abort_requested:
            self._residual_bytes.clear()
            self._sentinel_received = False
            self._drain_queue()
            self._abort_requested = False
            self._is_playing = False
            outdata[:] = b"\x00" * bytes_needed
            return

        # Pull chunks from queue into residual buffer
        while len(self._residual_bytes) < bytes_needed and not self._sentinel_received:
            try:
                chunk = self._queue.get_nowait()
                if chunk is None:
                    self._sentinel_received = True
                    break
                self._residual_bytes.extend(chunk)
            except queue.Empty:
                break

        # Output available bytes, zero-pad remainder if underrun
        if len(self._residual_bytes) > 0:
            avail = min(len(self._residual_bytes), bytes_needed)
            outdata[:avail] = bytes(self._residual_bytes[:avail])
            del self._residual_bytes[:avail]
            if avail < bytes_needed:
                outdata[avail:] = b"\x00" * (bytes_needed - avail)
        else:
            outdata[:] = b"\x00" * bytes_needed

        # Check for utterance completion
        if self._sentinel_received and len(self._residual_bytes) == 0:
            self._sentinel_received = False
            if self._is_playing:
                self._is_playing = False
                self._dispatch_complete()

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _dispatch_complete(self) -> None:
        if self._on_complete:
            cb = self._on_complete
            threading.Thread(target=cb, daemon=True).start()

    def _dispatch_interrupt(self) -> None:
        if self._on_interrupt:
            cb = self._on_interrupt
            threading.Thread(target=cb, daemon=True).start()

    def start_utterance(self) -> bool:
        """Prepare player for a new utterance, resetting the abort flag."""
        with self._lock:
            self._abort_requested = False
            self._sentinel_received = False
            self._drain_queue()
            self._is_playing = True
            return self._ensure_stream()

    def feed(self, chunk: bytes) -> None:
        """Feed a PCM chunk into the streaming playback queue."""
        if not self._abort_requested:
            self._queue.put(chunk)

    def finish(self) -> None:
        """Signal that all chunks for the current utterance have been generated."""
        self._queue.put(None)

    def abort(self) -> None:
        """Immediately abort active playback."""
        with self._lock:
            self._abort_requested = True
            self._sentinel_received = False
            self._is_playing = False
            self._dispatch_interrupt()

    def is_playing(self) -> bool:
        return self._is_playing

    def close(self) -> None:
        with self._lock:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._is_playing = False


# ─────────────────────────────────────────────────────────────────────────────
#  Piper TTS  (primary — local / offline)
# ─────────────────────────────────────────────────────────────────────────────

class PiperTTSEngine(TTSEngine):
    """Piper TTS — local, offline, low-latency chunked streaming.

    Requires:
      - ``piper-tts`` package (``pip install piper-tts``)
      - A Piper voice model (.onnx + .onnx.json).
        Path configured via PIPER_MODEL_PATH in .env (relative to project root).
    """

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.voice = None  # piper.voice.PiperVoice instance
        self.player: ChunkedStreamPlayer | None = None
        self._active_generation_id: int = 0
        self._lock = threading.Lock()

    # ── internal helpers ───────────────────────────────────────────────────

    def _get_model_path(self) -> str | None:
        """Return resolved absolute path to .onnx model, or None."""
        import os
        raw = self.settings.voice or os.getenv("PIPER_MODEL_PATH")
        if not raw:
            # Check default model location
            default_model = _PROJECT_ROOT / "models" / "tts" / "piper" / "en_US-lessac-medium.onnx"
            if default_model.exists():
                return str(default_model)
        return _resolve_model_path(raw)

    # ── TTSEngine interface ────────────────────────────────────────────────

    def initialize(self) -> bool:
        try:
            from piper.voice import PiperVoice  # piper-tts 1.6+

            model_path = self._get_model_path()
            if not model_path:
                logger.error(
                    "Piper: no model path. Set PIPER_MODEL_PATH in .env or "
                    "pass voice=<path> in TTSSettings."
                )
                return False

            if not Path(model_path).exists():
                logger.error(f"Piper model not found: {model_path}")
                return False

            logger.info(f"Loading Piper model: {model_path}")
            self.voice = PiperVoice.load(model_path)
            sample_rate = self.voice.config.sample_rate
            self.player = ChunkedStreamPlayer(sample_rate=sample_rate, channels=1)
            if self._playback_complete_callback or self._interrupt_callback:
                self.player.set_callbacks(self._playback_complete_callback, self._interrupt_callback)
            self.is_active = True
            logger.info("Piper TTS initialized with ChunkedStreamPlayer")
            return True

        except ImportError:
            logger.error("piper-tts not installed: pip install piper-tts")
            return False
        except Exception as e:
            logger.exception(f"Error initializing Piper TTS: {e}")
            return False

    def set_callbacks(
        self, complete: Callable[[], None], interrupt: Callable[[], None]
    ) -> None:
        super().set_callbacks(complete, interrupt)
        if self.player:
            self.player.set_callbacks(complete, interrupt)

    def add_text(self, text: str, interruptible: bool = True) -> bool:
        if not self.is_active:
            return False
        self._stream.append(text)
        return True

    def speak(self) -> bool:
        if not self.is_active or not self._stream or not self.voice or not self.player:
            return False

        text = " ".join(self._stream)
        self._stream.clear()

        with self._lock:
            self._active_generation_id += 1
            current_gen_id = self._active_generation_id

        if not self.player.start_utterance():
            return False

        self._is_playing = True

        def _producer():
            try:
                for audio_chunk in self.voice.synthesize(text):
                    with self._lock:
                        if self._active_generation_id != current_gen_id:
                            logger.debug("[PiperTTSEngine] Generation %d aborted mid-synthesis", current_gen_id)
                            return
                    self.player.feed(audio_chunk.audio_int16_bytes)

                with self._lock:
                    if self._active_generation_id == current_gen_id:
                        self.player.finish()
            except Exception as e:
                logger.exception(f"[PiperTTSEngine] Synthesis error: {e}")
                self.player.abort()
            finally:
                self._is_playing = False

        threading.Thread(target=_producer, daemon=True).start()
        return True

    def stop(self) -> bool:
        with self._lock:
            # Atomic ordering: bump generation ID FIRST to invalidate in-flight producer
            self._active_generation_id += 1
        self._stream.clear()
        self._is_playing = False
        if self.player:
            self.player.abort()
        self._emit_interrupt()
        return True

    def is_playing(self) -> bool:
        return self.player.is_playing() if self.player else self._is_playing

    def get_status(self) -> dict[str, Any]:
        return {
            "speaker": self.settings.speaker.value,
            "is_active": self.is_active,
            "is_playing": self.is_playing(),
            "model": self._get_model_path(),
            "chunks": len(self._stream),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Edge TTS  (fallback — online / Microsoft)
# ─────────────────────────────────────────────────────────────────────────────

class EdgeTTSEngine(TTSEngine):
    """Microsoft Edge TTS — online fallback, no subscription required."""

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.engine = None

    def initialize(self) -> bool:
        try:
            import edge_tts  # noqa: F401

            self.is_active = True
            logger.info("Edge TTS initialized")
            return True
        except ImportError:
            logger.error("edge-tts not installed: pip install edge-tts")
            return False
        except Exception as e:
            logger.error(f"Error initializing Edge TTS: {e}")
            return False

    def add_text(self, text: str, interruptible: bool = True) -> bool:
        if not self.is_active:
            return False
        self._stream.append(text)
        return True

    def speak(self) -> bool:
        if not self.is_active or not self._stream:
            return False

        try:
            import asyncio
            import edge_tts

            if not self._is_playing:
                self._is_playing = True

                voice_name = self.settings.voice or "en-US-AriaNeural"
                text_to_speak = " ".join(self._stream)
                self._stream.clear()

                communicate = edge_tts.Communicate(
                    text_to_speak,
                    voice_name,
                    rate=f"{(self.settings.rate - 1) * 100:+.0f}%",
                    volume=f"{(self.settings.volume - 1) * 100:+.0f}%",
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def _speak():
                    try:
                        import io
                        import sounddevice as sd
                        import soundfile as sf

                        audio_buf = io.BytesIO()
                        async for chunk in communicate.stream():
                            if not self._is_playing:
                                break
                            if chunk["type"] == "audio":
                                audio_buf.write(chunk["data"])

                        if self._is_playing and audio_buf.tell() > 0:
                            audio_buf.seek(0)
                            data, samplerate = sf.read(audio_buf)
                            sd.play(data, samplerate=samplerate)
                            sd.wait()
                            self._emit_complete()
                    except asyncio.CancelledError:
                        logger.info("Edge TTS speech interrupted")
                        self._emit_interrupt()
                    except Exception as e:
                        logger.error(f"Edge TTS stream error: {e}")
                    finally:
                        self._is_playing = False

                def _run():
                    loop.run_until_complete(_speak())
                    loop.close()

                threading.Thread(target=_run, daemon=True).start()

            return True

        except Exception as e:
            logger.error(f"Edge TTS speak error: {e}")
            self._is_playing = False
            return False

    def stop(self) -> bool:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self._stream.clear()
        self._is_playing = False
        self._emit_interrupt()
        return True

    def is_playing(self) -> bool:
        return self._is_playing

    def get_status(self) -> dict[str, Any]:
        return {
            "speaker": self.settings.speaker.value,
            "is_active": self.is_active,
            "is_playing": self._is_playing,
            "chunks": len(self._stream),
            "voice": self.settings.voice,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  TTSManger  (orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class TTSManger:
    """Streaming TTS Manager.

    Lifecycle
    ---------
    Lazy initialization: the underlying engine is created on the first call to
    :meth:`add_text`. Callers do not need to call :meth:`initialize` explicitly.
    Explicit :meth:`initialize` is idempotent — safe to call multiple times.

    Callbacks
    ---------
    Register callbacks via :meth:`set_callbacks` at any point — before or after
    the engine is created. They are stored and wired to the engine whenever it
    becomes available.
    """

    def __init__(self, settings: TTSSettings):
        self.settings = settings
        self.engine: TTSEngine | None = None
        self.fallback_engine: TTSEngine | None = None
        # Pending callbacks stored so they survive lazy initialization.
        self._pending_complete_callback: Callable[[], None] | None = None
        self._pending_interrupt_callback: Callable[[], None] | None = None
        self._last_added_text: list[str] = []

    def set_callbacks(
        self,
        complete: Callable[[], None],
        interrupt: Callable[[], None],
    ) -> None:
        """Register playback-complete and interrupt callbacks.

        Safe to call before or after the engine is created — callbacks are
        stored and applied to the engine whenever it becomes available.
        """
        self._pending_complete_callback = complete
        self._pending_interrupt_callback = interrupt
        if self.engine:
            self.engine.set_callbacks(complete, interrupt)
        if self.fallback_engine:
            self.fallback_engine.set_callbacks(complete, interrupt)

    def initialize(self) -> bool:
        """Initialize TTS engine. Idempotent — safe to call multiple times."""
        if self.engine and self.engine.is_active:
            return True

        try:
            speaker_enum = self._resolve_speaker()
            if speaker_enum is None:
                return False

            if speaker_enum == TTSSpeaker.PIPER:
                self.engine = PiperTTSEngine(self.settings)
            elif speaker_enum == TTSSpeaker.EDGE_TTS:
                self.engine = EdgeTTSEngine(self.settings)
            else:
                logger.error(f"Unsupported speaker: {speaker_enum}")
                return False

            ok = self.engine.initialize()
            if not ok and self.settings.fallback_speaker and self.settings.fallback_speaker != speaker_enum:
                logger.warning(
                    f"[TTS Fallback] Primary engine ({speaker_enum.value}) failed initialization. Engaging fallback ({self.settings.fallback_speaker.value})."
                )
                import sys
                try:
                    sys.stderr.write(
                        f"\n⚠️ [TTS Fallback] Primary TTS ({speaker_enum.value}) init failed. Using fallback {self.settings.fallback_speaker.value}.\n"
                    )
                    sys.stderr.flush()
                except Exception:
                    pass
                return self._init_fallback()

            if ok and self._pending_complete_callback:
                self.engine.set_callbacks(
                    self._pending_complete_callback,
                    self._pending_interrupt_callback,
                )
            return ok

        except Exception as e:
            logger.error(f"Error initializing TTS manager: {e}")
            if self.settings.fallback_speaker:
                return self._init_fallback()
            return False

    def _init_fallback(self) -> bool:
        fallback_speaker = self.settings.fallback_speaker
        if not fallback_speaker:
            return False
        fallback_settings = TTSSettings(
            speaker=fallback_speaker,
            voice=None,
            rate=self.settings.rate,
            pitch=self.settings.pitch,
            volume=self.settings.volume,
            streaming=self.settings.streaming,
            interruptible=self.settings.interruptible,
        )
        if fallback_speaker == TTSSpeaker.EDGE_TTS:
            self.fallback_engine = EdgeTTSEngine(fallback_settings)
        elif fallback_speaker == TTSSpeaker.PIPER:
            self.fallback_engine = PiperTTSEngine(fallback_settings)
        else:
            return False

        ok = self.fallback_engine.initialize()
        if ok and self._pending_complete_callback:
            self.fallback_engine.set_callbacks(
                self._pending_complete_callback,
                self._pending_interrupt_callback,
            )
        return ok

    def _resolve_speaker(self) -> TTSSpeaker | None:
        if isinstance(self.settings.speaker, str):
            for member in TTSSpeaker:
                if member.value == self.settings.speaker:
                    return member
            logger.error(f"Unsupported speaker string: {self.settings.speaker!r}")
            return None
        return self.settings.speaker

    def add_text(self, text: str) -> bool:
        """Add text to speech queue."""
        self._last_added_text.append(text)
        if not self.engine and not self.fallback_engine:
            logger.debug("TTS engine not yet initialized — attempting lazy init")
            if not self.initialize():
                logger.error("TTS lazy initialization failed; cannot add text")
                return False

        if self.engine and self.engine.is_active:
            if self.engine.add_text(text):
                return True

        if self.fallback_engine and self.fallback_engine.is_active:
            return self.fallback_engine.add_text(text)

        return False

    def speak(self) -> bool:
        """Start speaking."""
        if self.engine and self.engine.is_active:
            try:
                if self.engine.speak():
                    self._last_added_text.clear()
                    return True
            except Exception as e:
                logger.warning(f"[TTS Fallback] Primary engine speak() failed: {e}")

        # Engage fallback if primary failed or is not active
        if self.settings.fallback_speaker:
            logger.warning(
                f"[TTS Fallback] Engaging fallback engine ({self.settings.fallback_speaker.value}) for speech."
            )
            import sys
            try:
                sys.stderr.write(
                    f"\n⚠️ [TTS Fallback] Primary engine failed. Speaking via fallback {self.settings.fallback_speaker.value}.\n"
                )
                sys.stderr.flush()
            except Exception:
                pass

            if not self.fallback_engine:
                if not self._init_fallback():
                    return False

            # Transfer last added text to fallback engine
            if self._last_added_text:
                for t in self._last_added_text:
                    self.fallback_engine.add_text(t)
                self._last_added_text.clear()

            return self.fallback_engine.speak()

        return False

    def stop(self) -> bool:
        """Stop speaking."""
        ok1 = self.engine.stop() if self.engine else True
        ok2 = self.fallback_engine.stop() if self.fallback_engine else True
        self._last_added_text.clear()
        return ok1 and ok2

    def is_playing(self) -> bool:
        """Check if speaking."""
        if self.engine and self.engine.is_playing():
            return True
        if self.fallback_engine and self.fallback_engine.is_playing():
            return True
        return False

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        if self.engine:
            status = self.engine.get_status()
            status["fallback_active"] = self.fallback_engine is not None and self.fallback_engine.is_active
            return status
        return {"speaker": self.settings.speaker.value, "is_active": False}
