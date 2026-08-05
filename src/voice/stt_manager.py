"""
Speech-to-Text Manager

Streaming Speech-to-Text with partial results support.
Enables low-latency, real-time transcription.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class STTProvider(Enum):
    """Speech-to-Text providers."""

    WHISPER = "whisper"
    DEEPGRAM = "deepgram"
    VOSK = "vosk"
    AZURE = "azure"
    GOOGLE = "google"
    COHERE = "cohere"
    FUTURE = "future"


class STTSettings:
    """
    Configuration for STT.
    """

    def __init__(
        self,
        provider: STTProvider = STTProvider.WHISPER,
        language: str = "en-US",
        sample_rate: int = 16000,
        model_size: str = "base",
        verbose: bool = False,
        chunk_size: int = 20,
        processing_delay_ms: float = 50,
        max_alternatives: int = 1,
    ):
        self.provider = provider
        self.language = language
        self.sample_rate = sample_rate
        self.model_size = model_size
        self.verbose = verbose
        self.chunk_size = chunk_size
        self.processing_delay_ms = processing_delay_ms
        self.max_alternatives = max_alternatives

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "language": self.language,
            "sample_rate": self.sample_rate,
            "model_size": self.model_size,
            "verbose": self.verbose,
            "chunk_size": self.chunk_size,
            "processing_delay_ms": self.processing_delay_ms,
            "max_alternatives": self.max_alternatives,
        }


class STTEngine(ABC):
    """Abstract STT engine."""

    def __init__(self, settings: STTSettings):
        self.settings = settings
        self.is_active = False
        self._stream = None
        self._partial_callback: Callable[[str, float], None] | None = None
        self._final_callback: Callable[[str, float], None] | None = None
        self._error_callback: Callable[[str], None] | None = None
        self._total_duration = 0.0

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def process_chunk(self, audio_data: bytes) -> str:
        """Process audio chunk and return partial transcript."""
        pass

    @abstractmethod
    def finalize(self) -> str:
        """Finalize transcription and return complete transcript."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset for new session."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        pass

    def set_callbacks(
        self,
        partial: Callable[[str, float], None],
        final: Callable[[str, float], None],
        error: Callable[[str], None],
    ) -> None:
        self._partial_callback = partial
        self._final_callback = final
        self._error_callback = error

    def _emit_partial(self, text: str, duration: float) -> None:
        if self._partial_callback:
            self._partial_callback(text, duration)

    def _emit_final(self, text: str, duration: float) -> None:
        if self._final_callback:
            self._final_callback(text, duration)

    def _emit_error(self, error: str) -> None:
        if self._error_callback:
            self._error_callback(error)


class WhisperSTTEngine(STTEngine):
    """OpenAI Whisper STT."""

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.model = None

    def initialize(self) -> bool:
        try:
            import whisper

            self.model = whisper.load_model(self.settings.model_size)
            self.is_active = True
            logger.info(
                f"Whisper STT initialized with model: {self.settings.model_size}"
            )
            return True
        except ImportError:
            logger.error("whisper not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing Whisper: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        if not self.is_active:
            return ""

        try:
            if not self._stream:
                return ""

            # Process chunk
            result = self.model.transcribe(
                audio_data, language=self.settings.language, fp16=False
            )

            text = result["text"].strip()
            self._total_duration += len(audio_data) / self.settings.sample_rate / 2

            # Emit partial
            self._emit_partial(text, self._total_duration)

            return text

        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            self._emit_error(str(e))
            return ""

    def finalize(self) -> str:
        if not self.is_active:
            return ""

        try:
            # Finalize transcription
            result = self.model.transcribe(
                self._stream, language=self.settings.language, fp16=False
            )

            text = result["text"].strip()
            duration = self._total_duration

            # Emit final
            self._emit_final(text, duration)

            return text

        except Exception as e:
            logger.error(f"Error finalizing: {e}")
            self._emit_error(str(e))
            return ""

    def reset(self) -> None:
        self._stream = None
        self._total_duration = 0.0
        logger.debug("Whisper STT reset")

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.WHISPER.value,
            "is_active": self.is_active,
            "model": self.settings.model_size,
            "language": self.settings.language,
            "total_duration": self._total_duration,
        }


class DeepgramSTTEngine(STTEngine):
    """Deepgram STT."""

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.deepgram = None

    def initialize(self) -> bool:
        try:
            import deepgram

            key = self._get_api_key()
            if not key:
                logger.error("No Deepgram API key")
                return False

            self.deepgram = deepgram.DeepgramClient(key)
            self.is_active = True
            logger.info("Deepgram STT initialized")
            return True
        except ImportError:
            logger.error("deepgram not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing Deepgram: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        if not self.is_active:
            return ""

        try:
            if not self._stream:
                return ""

            # Process chunk
            result = self.deepgram.listen.v("1").live.transcribe(
                audio_data, model=self.settings.model_size
            )

            if result and result.alternatives:
                text = result.alternatives[0].transcript
                self._total_duration += len(audio_data) / self.settings.sample_rate / 2
                self._emit_partial(text, self._total_duration)
                return text

            return ""

        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            self._emit_error(str(e))
            return ""

    def finalize(self) -> str:
        if not self.is_active:
            return ""

        try:
            result = self.deepgram.listen.v("1").final_transcribe()
            if result and result.alternatives:
                text = result.alternatives[0].transcript
                duration = self._total_duration
                self._emit_final(text, duration)
                return text

            return ""

        except Exception as e:
            logger.error(f"Error finalizing: {e}")
            self._emit_error(str(e))
            return ""

    def reset(self) -> None:
        self._stream = None
        self._total_duration = 0.0

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.DEEPGRAM.value,
            "is_active": self.is_active,
            "model": self.settings.model_size,
            "language": self.settings.language,
        }

    def _get_api_key(self) -> str | None:
        import os

        return os.getenv("DEEPGRAM_API_KEY")


class VoskSTTEngine(STTEngine):
    """Vosk STT (offline)."""

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.model = None
        self.recognizer = None

    def initialize(self) -> bool:
        try:
            import vosk

            model_path = self._get_model_path()
            if not model_path:
                logger.error("No Vosk model found")
                return False

            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(
                self.model, self.settings.sample_rate
            )
            self.is_active = True
            logger.info("Vosk STT initialized")
            return True
        except ImportError:
            logger.error("vosk not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing Vosk: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        if not self.is_active:
            return ""

        try:
            if not self.recognizer:
                return ""

            result = self.recognizer.AcceptWaveform(audio_data)

            if result:
                text = self.recognizer.Result()
                if self._stream:
                    self._stream += text
                    duration = (
                        self._total_duration
                        + len(audio_data) / self.settings.sample_rate / 2
                    )
                    self._emit_partial(self._stream, duration)
                    return self._stream

            return ""

        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            self._emit_error(str(e))
            return ""

    def finalize(self) -> str:
        if not self.is_active:
            return ""

        try:
            result = self.recognizer.FinalResult()
            if result:
                text = result.get("text", "")
                duration = (
                    self._total_duration
                    + len(self._stream) / self.settings.sample_rate / 2
                )
                self._emit_final(text, duration)
                return text

            return ""

        except Exception as e:
            logger.error(f"Error finalizing: {e}")
            self._emit_error(str(e))
            return ""

    def reset(self) -> None:
        self._stream = ""
        self._total_duration = 0.0
        if self.recognizer:
            self.recognizer = vosk.KaldiRecognizer(
                self.model, self.settings.sample_rate
            )

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.VOSK.value,
            "is_active": self.is_active,
            "sample_rate": self.settings.sample_rate,
        }

    def _get_model_path(self) -> str | None:
        import os

        return os.getenv("VOSK_MODEL_PATH")


class STTManager:
    """Streaming STT Manager."""

    def __init__(self, settings: STTSettings):
        self.settings = settings
        self.engine: STTEngine | None = None
        self._stream_buffer = bytearray()

    def initialize(self) -> bool:
        """Initialize STT engine."""
        if self.engine:
            return self.engine.is_active

        try:
            if self.settings.provider == STTProvider.WHISPER:
                self.engine = WhisperSTTEngine(self.settings)
            elif self.settings.provider == STTProvider.DEEPGRAM:
                self.engine = DeepgramSTTEngine(self.settings)
            elif self.settings.provider == STTProvider.VOSK:
                self.engine = VoskSTTEngine(self.settings)
            else:
                logger.error(f"Unsupported provider: {self.settings.provider}")
                return False

            return self.engine.initialize()

        except Exception as e:
            logger.error(f"Error initializing STT manager: {e}")
            return False

    def process_audio(self, audio_data: bytes) -> str:
        """Process audio chunk."""
        if not self.engine or not self.engine.is_active:
            return ""

        self._stream_buffer.extend(audio_data)

        try:
            return self.engine.process_chunk(audio_data)
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return ""

    def finalize(self) -> str:
        """Finalize transcription."""
        if not self.engine or not self.engine.is_active:
            return ""

        try:
            return self.engine.finalize()
        except Exception as e:
            logger.error(f"Error finalizing: {e}")
            return ""

    def reset(self) -> None:
        """Reset for new session."""
        if self.engine:
            self.engine.reset()
        self._stream_buffer.clear()
        logger.debug("STT manager reset")

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        if self.engine:
            return self.engine.get_status()
        return {"provider": self.settings.provider.value, "is_active": False}
