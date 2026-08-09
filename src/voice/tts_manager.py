"""
Text-to-Speech Manager

Streaming Text-to-Speech with low-latency, real-time playback.
Enables responsive voice interactions.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TTSSpeaker(Enum):
    """Text-to-Speech speakers."""

    ELEVENLABS = "elevenlabs"
    EDGE_TTS = "edge_tts"
    PIPER = "piper"
    AZURE_TTS = "azure_tts"
    GOOGLE_TTS = "google_tts"
    LOCALLY = "locally"


class TTSSettings:
    """Configuration for TTS."""

    def __init__(
        self,
        speaker: TTSSpeaker = TTSSpeaker.EDGE_TTS,
        voice: str | None = None,
        rate: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        streaming: bool = True,
        interruptible: bool = True,
        fallback_speaker: TTSSpeaker | None = None,
    ):
        self.speaker = speaker
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.streaming = streaming
        self.interruptible = interruptible
        self.fallback_speaker = fallback_speaker

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
        self._stream = []
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


class EdgeTTSEngine(TTSEngine):
    """Microsoft Edge TTS."""

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.engine = None

    def initialize(self) -> bool:
        try:
            import edge_tts

            self.is_active = True
            logger.info("Edge TTS initialized")
            return True
        except ImportError:
            logger.error("edge-tts not installed")
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

                # Create voice name
                voice_name = self.settings.voice or "en-US-AriaNeural"

                # Create communicate
                communicate = edge_tts.Communicate(
                    self._stream[0],  # Speak first chunk
                    voice_name,
                    rate=f"{(self.settings.rate - 1) * 100:+d}",
                    pitch=f"{(self.settings.pitch - 1) * 100:+d}",
                )

                # Run in background
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def _speak():
                    try:
                        for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                yield chunk["data"]

                        self._emit_complete()

                    except asyncio.CancelledError:
                        logger.info("Speech interrupted")
                        self._emit_interrupt()

                    finally:
                        self._is_playing = False

                # Spawn task
                task = loop.create_task(_speak())

                # Schedule cleanup
                import threading

                threading.Thread(
                    target=lambda: self._cleanup_async(loop, task), daemon=True
                ).start()

            return True

        except Exception as e:
            logger.error(f"Error starting speech: {e}")
            return False

    def stop(self) -> bool:
        if not self.is_playing():
            return True

        self._emit_interrupt()
        self._stream.clear()
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

    def _cleanup_async(self, loop: asyncio.AbstractEventLoop, task):
        try:
            loop.run_until_complete(asyncio.sleep(1))  # Wait for completion
        except:
            pass
        finally:
            loop.close()


class PiperTTSEngine(TTSEngine):
    """Piper TTS (offline)."""

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.synthesizer = None

    def initialize(self) -> bool:
        try:
            import piper

            # Piper requires model path
            model_path = self._get_model_path()
            if not model_path:
                logger.error("No Piper model path")
                return False

            # Initialize
            self.synthesizer = piper.initialize(model_path)
            self.is_active = True
            logger.info("Piper TTS initialized")
            return True
        except ImportError:
            logger.error("piper not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing Piper: {e}")
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
            if not self._is_playing:
                self._is_playing = True

                # Load model
                model_path = self._get_model_path()
                voice_path = self.settings.voice

                # Synthesize
                output = piper.synthesize(
                    self.synthesizer, model_path, voice_path, self._stream[0]
                )

                # Play audio
                import sounddevice as sd

                audio_data = output.audio_data
                sample_rate = output.sample_rate

                self.output_stream = sd.OutputStream(
                    data=audio_data, samplerate=sample_rate
                )
                self.output_stream.start()

                # Wait for completion
                import time

                duration = len(audio_data) / sample_rate
                time.sleep(duration)

                self._emit_complete()
                self._is_playing = False
                self._stream.clear()

            return True

        except Exception as e:
            logger.error(f"Error starting speech: {e}")
            return False

    def stop(self) -> bool:
        if not self.is_playing():
            return True

        self._emit_interrupt()
        self._stream.clear()
        return True

    def is_playing(self) -> bool:
        return self._is_playing

    def get_status(self) -> dict[str, Any]:
        return {
            "speaker": self.settings.speaker.value,
            "is_active": self.is_active,
            "is_playing": self._is_playing,
            "chunks": len(self._stream),
        }

    def _get_model_path(self) -> str | None:
        import os

        return os.getenv("PIPER_MODEL_PATH")


class ElevenLabTTS(TTSEngine):
    """ElevenLabs TTS."""

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.client = None

    def initialize(self) -> bool:
        try:
            import elevenlabs.client

            key = self._get_api_key()
            if not key:
                logger.error("No ElevenLabs API key")
                return False

            self.client = elevenlabs.client.ElevenLabsClient(key)
            self.is_active = True
            logger.info("ElevenLabs TTS initialized")
            return True
        except ImportError:
            logger.error("elevenlabs not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing ElevenLabs: {e}")
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
            if not self._is_playing:
                self._is_playing = True

                # Generate speech
                voice_id = self.settings.voice or self._get_voice_id()

                response = self.client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=self._stream[0],
                    model_id=self._get_model_id(),
                    output_format="mp3_44100_128",
                )

                # Save and play
                import tempfile

                import sounddevice as sd
                import soundfile as sf

                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    f.write(response)
                    filepath = f.name

                # Play
                audio_data, sample_rate = sf.read(filepath)
                self.output_stream = sd.OutputStream(
                    data=audio_data, samplerate=sample_rate
                )
                self.output_stream.start()

                # Wait and cleanup
                import time

                duration = len(audio_data) / sample_rate
                time.sleep(duration)

                self._emit_complete()
                self._is_playing = False
                self._stream.clear()

            return True

        except Exception as e:
            logger.error(f"Error starting speech: {e}")
            return False

    def stop(self) -> bool:
        if not self.is_playing():
            return True

        self._emit_interrupt()
        self._stream.clear()
        return True

    def is_playing(self) -> bool:
        return self._is_playing

    def get_status(self) -> dict[str, Any]:
        return {
            "speaker": self.settings.speaker.value,
            "is_active": self.is_active,
            "is_playing": self._is_playing,
            "chunks": len(self._stream),
        }

    def _get_api_key(self) -> str | None:
        import os

        return os.getenv("ELEVENLABS_API_KEY")

    def _get_voice_id(self) -> str:
        # Default voice ID
        return "21m00Tcm4TlvDq8ikWAM"

    def _get_model_id(self) -> str:
        return "eleven_monolingual_v1"


class TTSManger:
    """Streaming TTS Manager."""

    def __init__(self, settings: TTSSettings):
        self.settings = settings
        self.engine: TTSEngine | None = None

    def initialize(self) -> bool:
        """Initialize TTS engine."""
        if self.engine and self.engine.is_active:
            return True

        try:
            if self.settings.speaker == TTSSpeaker.EDGE_TTS:
                self.engine = EdgeTTSEngine(self.settings)
            elif self.settings.speaker == TTSSpeaker.PIPER:
                self.engine = PiperTTSEngine(self.settings)
            elif self.settings.speaker == TTSSpeaker.ELEVENLABS:
                self.engine = ElevenLabTTS(self.settings)
            else:
                logger.error(f"Unsupported speaker: {self.settings.speaker}")
                return False

            return self.engine.initialize()

        except Exception as e:
            logger.error(f"Error initializing TTS manager: {e}")
            return False

    def add_text(self, text: str) -> bool:
        """Add text to speech queue."""
        if not self.engine:
            return False

        return self.engine.add_text(text)

    def speak(self) -> bool:
        """Start speaking."""
        if not self.engine:
            return False

        return self.engine.speak()

    def stop(self) -> bool:
        """Stop speaking."""
        if not self.engine:
            return False

        return self.engine.stop()

    def is_playing(self) -> bool:
        """Check if speaking."""
        if not self.engine:
            return False

        return self.engine.is_playing()

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        if self.engine:
            return self.engine.get_status()
        return {"speaker": self.settings.speaker.value, "is_active": False}
