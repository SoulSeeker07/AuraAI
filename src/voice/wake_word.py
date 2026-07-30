"""
Wake Word Detection

Detects wake words to activate voice interactions.
Supports multiple wake word engines with provider abstraction.
"""


import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Dict, Any
from enum import Enum


logger = logging.getLogger(__name__)


class WakeWordProvider(Enum):
    """Wake word detection providers."""
    PORCUPINE = "porcupine"  # Picovoice Porcupine
    OPEN_WAKE_WORD = "openwakeword"  # OpenWakeWord
    LOCAL = "local"  # Local wake word detection
    FUTURE = "future"  # Future wake word providers


class WakeWordEngine(ABC):
    """
    Abstract base class for wake word engines.
    
    Provides a provider-independent interface for wake word detection.
    """
    
    def __init__(self, sensitivity: float = 0.5, phrase_list: Optional[List[str]] = None):
        """
        Initialize wake word engine.
        
        Args:
            sensitivity: Sensitivity (0.0 - 1.0), higher = more sensitive
            phrase_list: List of wake words to detect
        """
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self.phrase_list = phrase_list or []
        self.enabled = True
        
        # Callbacks
        self.on_wake_word_detected: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        logger.info(f"Wake word engine initialized with {len(self.phrase_list)} phrases")
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the wake word engine.
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        """
        Process audio data for wake word detection.
        
        Args:
            audio_data: Audio data in PCM format
            sample_rate: Sample rate of audio
            
        Returns:
            True if wake word detected
        """
        pass
    
    @abstractmethod
    def is_active(self) -> bool:
        """
        Check if wake word detection is active.
        
        Returns:
            True if active
        """
        pass
    
    @abstractmethod
    def deactivate(self) -> None:
        """Deactivate wake word detection."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status.
        
        Returns:
            Dictionary with status information
        """
        pass
    
    def set_sensitivity(self, sensitivity: float) -> None:
        """Set wake word sensitivity."""
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        logger.debug(f"Wake word sensitivity set to {self.sensitivity}")


class PorcupineWakeWord(WakeWordEngine):
    """
    Porcupine wake word engine (Picovoice).
    
    Requires Picovoice license and access tokens.
    """
    
    def __init__(self, access_key: str, phrase_list: Optional[List[str]] = None, sensitivity: float = 0.5):
        """
        Initialize Porcupine wake word engine.
        
        Args:
            access_key: Picovoice access key
            phrase_list: List of wake words
            sensitivity: Sensitivity level
        """
        self.access_key = access_key
        self.porcupine = None
        self.is_initialized = False
        
        super().__init__(sensitivity=sensitivity, phrase_list=phrase_list)
    
    def initialize(self) -> bool:
        """Initialize Porcupine wake word engine."""
        try:
            import pvporcupine
            from pvporcupine import create_keyword_list
            
            # Create keyword list from phrases
            if self.phrase_list:
                keyword_list = create_keyword_list(self.phrase_list)
            else:
                keyword_list = []
            
            # Create Porcupine instance
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keyword_list=keyword_list,
                sensitivities=[self.sensitivity] * len(keyword_list)
            )
            
            self.is_initialized = True
            logger.info("Porcupine wake word engine initialized successfully")
            return True
            
        except ImportError:
            logger.error("pvporcupine not installed. Install with: pip install pvporcupine")
            return False
        except Exception as e:
            logger.error(f"Error initializing Porcupine: {e}")
            self.on_error(f"Failed to initialize Porcupine: {e}")
            return False
    
    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        """Process audio data for wake word detection."""
        if not self.is_initialized or not self.enabled:
            return False
        
        try:
            import pvporcupine
            
            # Process audio
            keyword_index = self.porcupine.process(audio_data)
            
            if keyword_index >= 0 and keyword_index < len(self.phrase_list):
                wake_word = self.phrase_list[keyword_index]
                logger.info(f"Wake word detected: {wake_word}")
                
                if self.on_wake_word_detected:
                    self.on_wake_word_detected(wake_word)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            if self.on_error:
                self.on_error(f"Error processing audio: {e}")
            return False
    
    def is_active(self) -> bool:
        """Check if wake word detection is active."""
        return self.is_initialized and self.enabled
    
    def deactivate(self) -> None:
        """Deactivate wake word detection."""
        self.enabled = False
        logger.debug("Porcupine wake word deactivated")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'provider': WakeWordProvider.PORCUPINE.value,
            'is_initialized': self.is_initialized,
            'enabled': self.enabled,
            'sensitivity': self.sensitivity,
            'phrase_count': len(self.phrase_list),
            'is_active': self.is_active()
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
            self.is_initialized = False
            logger.debug("Porcupine resources cleaned up")


class OpenWakeWord(WakeWordEngine):
    """
    OpenWakeWord wake word engine.
    
    Offline wake word detection using machine learning.
    """
    
    def __init__(self, phrase_list: Optional[List[str]] = None, sensitivity: float = 0.5):
        """
        Initialize OpenWakeWord engine.
        
        Args:
            phrase_list: List of wake words
            sensitivity: Sensitivity level
        """
        self.model = None
        self.is_initialized = False
        
        super().__init__(sensitivity=sensitivity, phrase_list=phrase_list)
    
    def initialize(self) -> bool:
        """Initialize OpenWakeWord engine."""
        try:
            import openwakeword
            
            # Create model
            self.model = openwakeword.AudioModel(
                model_path=None,  # Use default model
                pretrained=True
            )
            
            self.is_initialized = True
            logger.info("OpenWakeWord engine initialized successfully")
            return True
            
        except ImportError:
            logger.error("openwakeword not installed. Install with: pip install openwakeword")
            return False
        except Exception as e:
            logger.error(f"Error initializing OpenWakeWord: {e}")
            self.on_error(f"Failed to initialize OpenWakeWord: {e}")
            return False
    
    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        """Process audio data for wake word detection."""
        if not self.is_initialized or not self.enabled:
            return False
        
        try:
            import openwakeword
            
            # Convert bytes to numpy array
            audio = np.frombuffer(audio_data, dtype=np.int16)
            
            # Process audio
            predictions = self.model.predict(audio, is_speech=False)
            
            # Check for wake word matches
            if predictions:
                for keyword, probability in predictions.items():
                    if probability > self.sensitivity and keyword in self.phrase_list:
                        logger.info(f"Wake word detected: {keyword} ({probability:.2f})")
                        
                        if self.on_wake_word_detected:
                            self.on_wake_word_detected(keyword)
                        
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            if self.on_error:
                self.on_error(f"Error processing audio: {e}")
            return False
    
    def is_active(self) -> bool:
        """Check if wake word detection is active."""
        return self.is_initialized and self.enabled
    
    def deactivate(self) -> None:
        """Deactivate wake word detection."""
        self.enabled = False
        logger.debug("OpenWakeWord deactivated")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'provider': WakeWordProvider.OPEN_WAKE_WORD.value,
            'is_initialized': self.is_initialized,
            'enabled': self.enabled,
            'sensitivity': self.sensitivity,
            'phrase_count': len(self.phrase_list),
            'is_active': self.is_active()
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if self.model:
            del self.model
            self.model = None
            self.is_initialized = False
            logger.debug("OpenWakeWord resources cleaned up")


class LocalWakeWord(WakeWordEngine):
    """
    Simple local wake word detection.
    
    Uses energy-based detection as a simple wake word trigger.
    """
    
    def __init__(self, phrase_list: Optional[List[str]] = None, sensitivity: float = 0.5):
        """
        Initialize local wake word engine.
        
        Args:
            phrase_list: List of wake words (currently not used)
            sensitivity: Energy threshold
        """
        self.energy_threshold = 0.3 * sensitivity
        self.is_initialized = True
        self.last_speech_energy = 0.0
        
        super().__init__(sensitivity=sensitivity, phrase_list=phrase_list)
    
    def initialize(self) -> bool:
        """Initialize local wake word engine."""
        # Always initialized as it's simple
        return True
    
    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        """Process audio data for wake word detection."""
        if not self.enabled:
            return False
        
        try:
            import numpy as np
            
            # Calculate energy
            audio = np.frombuffer(audio_data, dtype=np.int16)
            energy = np.sqrt(np.mean(audio ** 2))
            max_amplitude = 32768
            energy_norm = energy / max_amplitude
            
            self.last_speech_energy = energy_norm
            
            # Check if energy exceeds threshold
            if energy_norm > self.energy_threshold:
                logger.info("Local wake word detected (energy threshold)")
                
                if self.on_wake_word_detected:
                    self.on_wake_word_detected("local_wake")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            if self.on_error:
                self.on_error(f"Error processing audio: {e}")
            return False
    
    def is_active(self) -> bool:
        """Check if wake word detection is active."""
        return self.enabled
    
    def deactivate(self) -> None:
        """Deactivate wake word detection."""
        self.enabled = False
        logger.debug("Local wake word deactivated")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'provider': WakeWordProvider.LOCAL.value,
            'is_initialized': self.is_initialized,
            'enabled': self.enabled,
            'energy_threshold': self.energy_threshold,
            'last_energy': self.last_speech_energy,
            'phrase_count': len(self.phrase_list),
            'is_active': self.is_active()
        }


class WakeWordManager:
    """
    Manages wake word detection.
    
    Provides a unified interface for wake word detection across different providers.
    """
    
    def __init__(
        self,
        provider: WakeWordProvider = WakeWordProvider.LOCAL,
        sensitivity: float = 0.5,
        phrase_list: Optional[List[str]] = None
    ):
        """
        Initialize wake word manager.
        
        Args:
            provider: Wake word provider to use
            sensitivity: Detection sensitivity
            phrase_list: List of wake words to detect
        """
        self.provider = provider
        self.sensitivity = sensitivity
        self.phrase_list = phrase_list or []
        
        # Engine instances
        self.engine: Optional[WakeWordEngine] = None
        
        # Callbacks
        self.on_wake_word_detected: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Status
        self.is_active = False
        self.is_initialized = False
        
        logger.info(f"Wake word manager initialized with provider: {provider.value}")
    
    def initialize(self) -> bool:
        """Initialize wake word engine."""
        if self.is_initialized:
            return True
        
        try:
            # Create engine based on provider
            if self.provider == WakeWordProvider.PORCUPINE:
                # Need access key
                access_key = self._get_access_key()
                if not access_key:
                    logger.error("No access key provided for Porcupine")
                    return False
                self.engine = PorcupineWakeWord(
                    access_key=access_key,
                    phrase_list=self.phrase_list,
                    sensitivity=self.sensitivity
                )
            elif self.provider == WakeWordProvider.OPEN_WAKE_WORD:
                self.engine = OpenWakeWord(
                    phrase_list=self.phrase_list,
                    sensitivity=self.sensitivity
                )
            else:  # LOCAL
                self.engine = LocalWakeWord(
                    phrase_list=self.phrase_list,
                    sensitivity=self.sensitivity
                )
            
            # Set callbacks
            self.engine.on_wake_word_detected = self.on_wake_word_detected
            self.engine.on_error = self.on_error
            
            # Initialize engine
            if not self.engine.initialize():
                return False
            
            self.is_initialized = True
            logger.info("Wake word manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing wake word manager: {e}")
            self.on_error(f"Failed to initialize wake word manager: {e}")
            return False
    
    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        """Process audio data for wake word detection."""
        if not self.is_initialized or not self.is_active:
            return False
        
        return self.engine.process_audio(audio_data, sample_rate)
    
    def activate(self) -> bool:
        """Activate wake word detection."""
        if not self.is_initialized:
            return self.initialize()
        
        self.engine.enabled = True
        self.is_active = True
        logger.debug("Wake word detection activated")
        return True
    
    def deactivate(self) -> bool:
        """Deactivate wake word detection."""
        if self.engine:
            self.engine.deactivate()
        
        self.is_active = False
        logger.debug("Wake word detection deactivated")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        if self.engine:
            status = self.engine.get_status()
            status['manager_active'] = self.is_active
            return status
        
        return {
            'provider': self.provider.value,
            'is_initialized': self.is_initialized,
            'is_active': self.is_active,
            'sensitivity': self.sensitivity
        }
    
    def set_sensitivity(self, sensitivity: float) -> None:
        """Set wake word sensitivity."""
        self.sensitivity = sensitivity
        if self.engine:
            self.engine.set_sensitivity(sensitivity)
    
    def set_phrases(self, phrase_list: List[str]) -> None:
        """Update wake word phrases."""
        self.phrase_list = phrase_list
        if self.engine and hasattr(self.engine, 'phrase_list'):
            self.engine.phrase_list = phrase_list
            logger.info(f"Wake word phrases updated to {len(phrase_list)}")
    
    def _get_access_key(self) -> Optional[str]:
        """
        Get access key from environment or config.
        
        Returns:
            Access key or None
        """
        import os
        
        # Try environment variable
        access_key = os.getenv('PORCUPINE_ACCESS_KEY')
        if access_key:
            return access_key
        
        # Try config file (example)
        try:
            import configparser
            config = configparser.ConfigParser()
            if config.read('config.ini'):
                return config.get('wake_word', 'access_key', fallback=None)
        except Exception:
            pass
        
        return None
