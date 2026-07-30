"""
Voice System Models

Core data models for the Voice System including VoiceContext, ConversationState,
VoiceProvider, and conversation management.
"""


import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """
    Conversation state for voice interactions.

    States represent the lifecycle of a voice conversation.
    """
    IDLE = "idle"  # System ready, not listening
    WAKE_LISTENING = "wake_listening"  # Listening for wake word
    ACTIVE_LISTENING = "active_listening"  # Listening for commands
    THINKING = "thinking"  # Processing user input with brain
    EXECUTING = "executing"  # Executing tools/commands
    SPEAKING = "speaking"  # Generating and playing TTS response
    INTERRUPTED = "interrupted"  # User interrupted during speech
    PAUSED = "paused"  # Conversation paused (manual or system)
    ERROR = "error"  # Error occurred during conversation
    COMPLETE = "complete"  # Conversation completed


class VoiceProvider(Enum):
    """
    Speech-to-Text providers.
    """
    WHISPER = "whisper"  # OpenAI Whisper
    DEEPGRAM = "deepgram"  # Deepgram
    VOSK = "vosk"  # Vosk (offline)
    AZURE = "azure"  # Azure Speech Services
    GOOGLE = "google"  # Google Speech-to-Text
    COHERE = "cohere"  # Cohere Whisper API
    FUTURE = "future"  # Future STT providers


class TTSSpeaker(Enum):
    """
    Text-to-Speech speakers/providers.
    """
    ELEVENLABS = "elevenlabs"  # ElevenLabs
    EDGE_TTS = "edge_tts"  # Microsoft Edge TTS
    PIPER = "piper"  # Piper (offline)
    AZURE_TTS = "azure_tts"  # Azure TTS
    GOOGLE_TTS = "google_tts"  # Google TTS
    LOCALLY = "locally"  # Local TTS (system voice)
    FUTURE = "future"  # Future TTS providers


class WakeWordProvider(Enum):
    """
    Wake word detection providers.
    """
    PORCUPINE = "porcupine"  # Picovoice Porcupine
    OPEN_WAKE_WORD = "openwakeword"  # OpenWakeWord
    LOCAL = "local"  # Local wake word detection
    FUTURE = "future"  # Future wake word providers


class InterruptReason(Enum):
    """
    Reasons for interrupting a conversation.
    """
    USER_INTERRUPT = "user_interrupt"  # User explicitly interrupted
    SYSTEM_INTERRUPT = "system_interrupt"  # System interrupted (timeout, error, etc.)
    NEW_REQUEST = "new_request"  # New request detected
    TIME_LIMIT = "time_limit"  # Conversation timeout
    ERROR = "error"  # Error occurred


class VADMode(Enum):
    """
    Voice Activity Detection modes.
    """
    SILENCE_THRESHOLD = "silence_threshold"  # Based on silence duration
    ENERGY_THRESHOLD = "energy_threshold"  # Based on audio energy
    BOTH = "both"  # Use both silence and energy
    HYBRID = "hybrid"  # Adaptive VAD


@dataclass
class VoiceContext:
    """
    Structured voice context containing analysis results.

    Contains transcript information, confidence scores, and metadata
    for voice interactions with Aura Brain.
    """
    # Transcript data
    transcript: str  # Complete transcript
    partial_transcript: str = ""  # Current partial transcript (streaming)
    final_transcript: str = ""  # Most recent final transcript

    # Confidence and quality
    confidence: float = 0.0  # Overall confidence (0.0 - 1.0)
    language: str = "en-US"  # Detected language
    speaker_id: Optional[str] = None  # Speaker identification (future)

    # Audio metadata
    duration: float = 0.0  # Duration of utterance in seconds
    sample_rate: int = 16000  # Audio sample rate
    audio_sample_count: int = 0  # Number of audio samples
    audio_metadata: Dict[str, Any] = field(default_factory=dict)  # Additional audio info

    # Conversation metadata
    interruptions: int = 0  # Number of interruptions
    last_interrupt_time: Optional[datetime] = None  # When last interruption occurred
    is_interrupted: bool = False  # Was this utterance interrupted?

    # Processing metadata
    processing_time_ms: float = 0.0  # Time to process utterance
    stt_model: Optional[str] = None  # STT model used
    vad_model: Optional[str] = None  # VAD model used
    provider: Optional[str] = None  # STT provider used

    # Recognition quality
    has_pauses: bool = False  # Transcript contains pauses
    is_continuous: bool = True  # Was continuous speech detected

    # Contextual information
    keywords: List[str] = field(default_factory=list)  # Detected keywords
    entities: List[str] = field(default_factory=list)  # Detected entities
    intent: Optional[str] = None  # Detected intent (if applicable)

    def __post_init__(self):
        """Validate dataclass fields."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.duration = max(0.0, self.duration)
        self.sample_rate = max(8000, min(48000, self.sample_rate))
        self.interruptions = max(0, self.interruptions)

    def update_partial(self, partial: str):
        """Update partial transcript."""
        self.partial_transcript = partial

    def finalize(self, full_transcript: str):
        """Finalize transcript with full content."""
        self.final_transcript = full_transcript
        self.transcript = full_transcript

    def add_interruption(self):
        """Record an interruption event."""
        self.interruptions += 1
        self.is_interrupted = True
        self.last_interrupt_time = datetime.now()

    def reset(self):
        """Reset context for new utterance."""
        self.partial_transcript = ""
        self.final_transcript = ""
        self.confidence = 0.0
        self.interruptions = 0
        self.is_interrupted = False
        self.keywords.clear()
        self.entities.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'transcript': self.transcript,
            'partial_transcript': self.partial_transcript,
            'final_transcript': self.final_transcript,
            'confidence': self.confidence,
            'language': self.language,
            'speaker_id': self.speaker_id,
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'audio_sample_count': self.audio_sample_count,
            'audio_metadata': self.audio_metadata,
            'interruptions': self.interruptions,
            'last_interrupt_time': self.last_interrupt_time.isoformat() if self.last_interrupt_time else None,
            'is_interrupted': self.is_interrupted,
            'processing_time_ms': self.processing_time_ms,
            'stt_model': self.stt_model,
            'vad_model': self.vad_model,
            'provider': self.provider,
            'has_pauses': self.has_pauses,
            'is_continuous': self.is_continuous,
            'keywords': self.keywords,
            'entities': self.entities,
            'intent': self.intent
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VoiceContext':
        """Create VoiceContext from dictionary."""
        return cls(**data)


@dataclass
class ConversationSession:
    """
    A single voice conversation session.

    Tracks conversation state, timing, and metadata.
    """
    session_id: str  # Unique session identifier
    conversation_id: str  # Reference to conversation in other systems
    state: ConversationState = ConversationState.IDLE
    language: str = "en-US"
    device: Optional[Dict[str, Any]] = None  # Audio device info

    # Timing
    wake_time: Optional[datetime] = None  # When session started
    active_time: Optional[datetime] = None  # When conversation became active
    last_activity_time: Optional[datetime] = None  # When last activity occurred
    duration: float = 0.0  # Total duration in seconds

    # Conversation metadata
    utterance_count: int = 0  # Number of utterances processed
    interruption_count: int = 0  # Number of interruptions
    error_count: int = 0  # Number of errors

    # Active task
    active_task: Optional[str] = None  # Currently executing task
    task_start_time: Optional[datetime] = None

    # Configuration
    silence_threshold: float = 1.0  # Silence duration in seconds
    energy_threshold: float = 0.1  # Energy threshold (0.0 - 1.0)
    vad_mode: VADMode = VADMode.BOTH

    # Latency tracking
    latency_stats: Dict[str, float] = field(default_factory=dict)  # Per-stage latencies
    success_rate: float = 0.0  # Success rate of conversations

    def __post_init__(self):
        """Initialize session ID if not provided."""
        if not self.session_id:
            from uuid import uuid4
            self.session_id = str(uuid4())

    def start(self):
        """Start the session."""
        self.wake_time = datetime.now()
        self.state = ConversationState.ACTIVE_LISTENING

    def activate(self):
        """Activate conversation state."""
        self.active_time = datetime.now()
        self.last_activity_time = datetime.now()
        self.state = ConversationState.ACTIVE_LISTENING

    def update_state(self, state: ConversationState):
        """Update session state."""
        self.state = state
        self.last_activity_time = datetime.now()

    def record_utterance(self, context: VoiceContext):
        """Record a processed utterance."""
        self.utterance_count += 1
        self.interruption_count += context.interruptions

    def start_task(self, task: str):
        """Start an active task."""
        self.active_task = task
        self.task_start_time = datetime.now()
        self.state = ConversationState.EXECUTING

    def end_task(self):
        """End the active task."""
        self.active_task = None
        self.task_start_time = None

    def record_error(self):
        """Record an error event."""
        self.error_count += 1

    def update_latency(self, stage: str, latency_ms: float):
        """Update latency statistics for a stage."""
        if stage not in self.latency_stats:
            self.latency_stats[stage] = latency_ms
        else:
            self.latency_stats[stage] = (
                self.latency_stats[stage] + latency_ms
            ) / 2  # Simple average

    def get_averaged_latency(self, stage: str) -> float:
        """Get averaged latency for a stage."""
        return self.latency_stats.get(stage, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'conversation_id': self.conversation_id,
            'state': self.state.value,
            'language': self.language,
            'device': self.device,
            'wake_time': self.wake_time.isoformat() if self.wake_time else None,
            'active_time': self.active_time.isoformat() if self.active_time else None,
            'last_activity_time': self.last_activity_time.isoformat() if self.last_activity_time else None,
            'duration': self.duration,
            'utterance_count': self.utterance_count,
            'interruption_count': self.interruption_count,
            'error_count': self.error_count,
            'active_task': self.active_task,
            'task_start_time': self.task_start_time.isoformat() if self.task_start_time else None,
            'silence_threshold': self.silence_threshold,
            'energy_threshold': self.energy_threshold,
            'vad_mode': self.vad_mode.value,
            'latency_stats': self.latency_stats,
            'success_rate': self.success_rate
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationSession':
        """Create ConversationSession from dictionary."""
        # Convert state enum
        if 'state' in data:
            try:
                data['state'] = ConversationState(data['state'])
            except ValueError:
                pass

        # Convert VADMode enum
        if 'vad_mode' in data:
            try:
                data['vad_mode'] = VADMode(data['vad_mode'])
            except ValueError:
                pass

        return cls(**data)


@dataclass
class InterruptEvent:
    """
    Represents an interruption event.
    """
    reason: InterruptReason
    timestamp: datetime
    interrupter: str = "user"  # "user", "system", "background"
    utterance_before: Optional[str] = None  # Utterance that was interrupted
    was_speaking: bool = False  # Was Aura speaking when interrupted

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'reason': self.reason.value,
            'timestamp': self.timestamp.isoformat(),
            'interrupter': self.interrupter,
            'utterance_before': self.utterance_before,
            'was_speaking': self.was_speaking
        }


@dataclass
class TTSRequest:
    """
    Request for Text-to-Speech.
    """
    text: str  # Text to speak
    speaker: TTSSpeaker = TTSSpeaker.EDGE_TTS  # Speaker to use
    voice: Optional[str] = None  # Voice name (if applicable)
    rate: float = 1.0  # Speaking rate (0.5 - 2.0)
    pitch: float = 1.0  # Pitch (0.5 - 2.0)
    volume: float = 1.0  # Volume (0.0 - 2.0)
    interruptible: bool = True  # Can be interrupted by user

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'text': self.text,
            'speaker': self.speaker.value,
            'voice': self.voice,
            'rate': self.rate,
            'pitch': self.pitch,
            'volume': self.volume,
            'interruptible': self.interruptible
        }


@dataclass
class STTSettings:
    """
    Settings for Speech-to-Text.
    """
    provider: VoiceProvider = VoiceProvider.WHISPER
    language: str = "en-US"
    sample_rate: int = 16000
    model_size: str = "base"  # tiny, base, small, medium, large
    verbose: bool = False  # Print processing details
    chunk_size: int = 20  # STT chunk size for streaming
    processing_delay_ms: float = 50  # Delay between chunks
    max_alternatives: int = 1  # Maximum transcript alternatives

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'provider': self.provider.value,
            'language': self.language,
            'sample_rate': self.sample_rate,
            'model_size': self.model_size,
            'verbose': self.verbose,
            'chunk_size': self.chunk_size,
            'processing_delay_ms': self.processing_delay_ms,
            'max_alternatives': self.max_alternatives
        }


@dataclass
class TTSSettings:
    """
    Settings for Text-to-Speech.
    """
    speaker: TTSSpeaker = TTSSpeaker.EDGE_TTS
    voice: Optional[str] = None
    rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    streaming: bool = True  # Enable streaming TTS
    interruptible: bool = True  # Allow interruption
    fallback_speaker: Optional[TTSSpeaker] = None  # Fallback if primary fails
    silence_before_ms: int = 200  # Silence before response
    silence_after_ms: int = 100  # Silence after response

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'speaker': self.speaker.value,
            'voice': self.voice,
            'rate': self.rate,
            'pitch': self.pitch,
            'volume': self.volume,
            'streaming': self.streaming,
            'interruptible': self.interruptible,
            'fallback_speaker': self.fallback_speaker.value if self.fallback_speaker else None,
            'silence_before_ms': self.silence_before_ms,
            'silence_after_ms': self.silence_after_ms
        }


@dataclass
class WakeWordSettings:
    """
    Settings for Wake Word detection.
    """
    provider: WakeWordProvider = WakeWordProvider.PORCUPINE
    phrase: List[str] = field(default_factory=lambda: ["aura", "hey aura"])
    sensitivity: float = 0.5  # Sensitivity (0.0 - 1.0)
    enable_background: bool = True  # Continue detection when not in conversation
    silence_threshold: float = 1.5  # Silence duration in seconds
    energy_threshold: float = 0.3  # Energy threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'provider': self.provider.value,
            'phrase': self.phrase,
            'sensitivity': self.sensitivity,
            'enable_background': self.enable_background,
            'silence_threshold': self.silence_threshold,
            'energy_threshold': self.energy_threshold
        }


@dataclass
class VoiceSettings:
    """
    Overall voice system settings.
    """
    stt_settings: STTSettings = field(default_factory=STTSettings)
    tts_settings: TTSSettings = field(default_factory=TTSSettings)
    wake_word_settings: WakeWordSettings = field(default_factory=WakeWordSettings)
    vad_mode: VADMode = VADMode.BOTH
    silence_threshold: float = 1.0  # End-of-speech silence duration
    energy_threshold: float = 0.1  # End-of-speech energy threshold
    enable_interruptibility: bool = True  # Enable barge-in capability
    enable_streaming: bool = True  # Enable streaming STT/TTS
    log_level: str = "INFO"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'stt_settings': self.stt_settings.to_dict(),
            'tts_settings': self.tts_settings.to_dict(),
            'wake_word_settings': self.wake_word_settings.to_dict(),
            'vad_mode': self.vad_mode.value,
            'silence_threshold': self.silence_threshold,
            'energy_threshold': self.energy_threshold,
            'enable_interruptibility': self.enable_interruptibility,
            'enable_streaming': self.enable_streaming,
            'log_level': self.log_level
        }
