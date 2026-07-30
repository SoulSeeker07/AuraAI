"""
Interruption Manager

Manages interruptibility (barge-in) capability.
Handles user interruptions during Aura's speech.
"""


import logging
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime


logger = logging.getLogger(__name__)


class InterruptionReason(Enum):
    """Reasons for interruptions."""
    USER_INTERRUPT = "user_interrupt"  # User explicitly interrupted
    SYSTEM_INTERRUPT = "system_interrupt"  # System interrupted (timeout, error, etc.)
    NEW_REQUEST = "new_request"  # New request detected
    TIME_LIMIT = "time_limit"  # Conversation timeout
    ERROR = "error"  # Error occurred


class InterruptionState(Enum):
    """Interruption state."""
    IDLE = "idle"  # Not interrupted
    INTERRUPTED = "interrupted"  # Currently interrupted
    RESUMING = "resuming"  # Resuming from interruption
    COMPLETE = "complete"  # Interruption complete


class InterruptionManager:
    """
    Manages interruptibility for voice conversations.
    
    Handles barge-in capability and manages interruption events.
    """
    
    def __init__(
        self,
        enable_interruptibility: bool = True,
        silence_threshold: float = 1.0,
        energy_threshold: float = 0.1,
        interruptible_duration: float = 2.0
    ):
        """
        Initialize interruption manager.
        
        Args:
            enable_interruptibility: Enable/disable barge-in capability
            silence_threshold: Silence duration to trigger interruption
            energy_threshold: Energy threshold to detect user speech
            interruptible_duration: Maximum duration Aura can be interrupted
        """
        self.enable_interruptibility = enable_interruptibility
        self.silence_threshold = silence_threshold
        self.energy_threshold = energy_threshold
        self.interruptible_duration = interruptible_duration
        
        # State tracking
        self.state = InterruptionState.IDLE
        self.interrupt_start_time: Optional[datetime] = None
        self.interrupt_reason: Optional[InterruptionReason] = None
        self.current_interruption_count = 0
        self.total_interruptions = 0
        
        # Callbacks
        self.on_interrupt_start: Optional[Callable[[InterruptionReason], None]] = None
        self.on_interrupt_end: Optional[Callable[[], None]] = None
        self.on_interrupt_detected: Optional[Callable[[str], None]] = None  # User speech detected
        
        # Statistics
        self.total_interrupt_time = 0.0  # Total time Aura was interrupted
        self.speech_interrupts = 0  # Interruptions during speech
        self.idle_interrupts = 0  # Interruptions during silence
        
        logger.info("Interruption manager initialized")
    
    def update_state(self, state: InterruptionState) -> None:
        """Update interruption state."""
        self.state = state
        logger.debug(f"Interruption state updated: {state.value}")
    
    def detect_user_interrupt(self) -> bool:
        """
        Detect if user has started speaking (triggering interruption).
        
        Returns:
            True if user interrupt detected
        """
        if not self.enable_interruptibility:
            return False
        
        if self.state == InterruptionState.INTERRUPTED:
            return True
        
        # In reality, this would check VAD or audio input
        # For now, we'll use a simple simulation
        return False
    
    def start_interrupt(self, reason: InterruptionReason) -> None:
        """
        Start an interruption event.
        
        Args:
            reason: Reason for interruption
        """
        if not self.enable_interruptibility:
            return
        
        if self.state != InterruptionState.IDLE:
            return
        
        self.state = InterruptionState.INTERRUPTED
        self.interrupt_start_time = datetime.now()
        self.interrupt_reason = reason
        self.current_interruption_count += 1
        self.total_interruptions += 1
        
        if reason == InterruptionReason.USER_INTERRUPT:
            self.speech_interrupts += 1
        else:
            self.idle_interrupts += 1
        
        logger.info(f"Interruption started: {reason.value} (count: {self.current_interruption_count})")
        
        if self.on_interrupt_start:
            self.on_interrupt_start(reason)
    
    def end_interrupt(self) -> None:
        """End current interruption."""
        if not self.enable_interruptibility:
            return
        
        if self.state != InterruptionState.INTERRUPTED:
            return
        
        if self.interrupt_start_time:
            duration = (datetime.now() - self.interrupt_start_time).total_seconds()
            self.total_interrupt_time += duration
            self.interrupt_start_time = None
        
        self.state = InterruptionState.IDLE
        logger.info(f"Interruption ended (total interrupted time: {self.total_interrupt_time:.2f}s)")
        
        if self.on_interrupt_end:
            self.on_interrupt_end()
    
    def check_interruptible(self) -> bool:
        """
        Check if Aura can be interrupted.
        
        Returns:
            True if interruptible
        """
        if not self.enable_interruptibility:
            return False
        
        if self.state == InterruptionState.INTERRUPTED:
            return False
        
        if self.interruptible_duration > 0:
            if self.interrupt_start_time:
                duration = (datetime.now() - self.interrupt_start_time).total_seconds()
                if duration > self.interruptible_duration:
                    logger.warning("Interruptible duration exceeded")
                    return False
        
        return True
    
    def set_interruptible_duration(self, duration: float) -> None:
        """Set maximum interruptible duration."""
        self.interruptible_duration = duration
        logger.info(f"Interruptible duration set to {duration}s")
    
    def reset(self) -> None:
        """Reset interruption state."""
        self.state = InterruptionState.IDLE
        self.interrupt_start_time = None
        self.interrupt_reason = None
        self.current_interruption_count = 0
        logger.debug("Interruption manager reset")
    
    def set_enable_interruptibility(self, enable: bool) -> None:
        """Enable or disable interruptibility."""
        self.enable_interruptibility = enable
        if not enable:
            self.end_interrupt()
        logger.info(f"Interruptibility {'enabled' if enable else 'disabled'}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get interruption statistics."""
        return {
            'state': self.state.value,
            'is_interruptible': self.check_interruptible(),
            'current_interruption_count': self.current_interruption_count,
            'total_interruptions': self.total_interruptions,
            'total_interrupt_time': self.total_interrupt_time,
            'speech_interrupts': self.speech_interrupts,
            'idle_interrupts': self.idle_interrupts,
            'enable_interruptibility': self.enable_interruptibility,
            'interruptible_duration': self.interruptible_duration
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'state': self.state.value,
            'interrupt_start_time': self.interrupt_start_time.isoformat() if self.interrupt_start_time else None,
            'interrupt_reason': self.interrupt_reason.value if self.interrupt_reason else None,
            'current_interruption_count': self.current_interruption_count,
            'total_interruptions': self.total_interruptions,
            'total_interrupt_time': self.total_interrupt_time,
            'speech_interrupts': self.speech_interrupts,
            'idle_interrupts': self.idle_interrupts,
            'enable_interruptibility': self.enable_interruptibility,
            'interruptible_duration': self.interruptible_duration
        }


class BargeInHandler:
    """
    Barge-in handler for detecting and managing user interruptions.
    
    Works with VAD to detect when user starts speaking while Aura is speaking.
    """
    
    def __init__(
        self,
        vad_callback: Callable[[], None],
        on_interrupt: Callable[[str], None],
        on_resume: Callable[[], None]
    ):
        """
        Initialize barge-in handler.
        
        Args:
            vad_callback: Callback for VAD speech detection
            on_interrupt: Callback when user interrupts
            on_resume: Callback when user stops speaking (Aura can resume)
        """
        self.vad_callback = vad_callback
        self.on_interrupt = on_interrupt
        self.on_resume = on_resume
        
        self.user_speaking = False
        self.aura_speaking = False
        self.pending_resume = False
        
        logger.info("Barge-in handler initialized")
    
    def on_vad_speech_start(self) -> None:
        """Called when user starts speaking."""
        if self.aura_speaking:
            logger.info("User speaking detected - interrupting Aura")
            self.user_speaking = True
            self.on_interrupt("user_interrupt")
        else:
            logger.debug("User speaking detected (not interrupting Aura)")
    
    def on_vad_speech_end(self) -> None:
        """Called when user stops speaking."""
        if self.user_speaking:
            logger.info("User speech ended")
            self.user_speaking = False
            self.on_resume()
    
    def set_aura_speaking(self, speaking: bool) -> None:
        """Set Aura's speaking state."""
        self.aura_speaking = speaking
        logger.debug(f"Aura speaking: {speaking}")
    
    def check_for_interrupt(self) -> bool:
        """
        Check if user is speaking and Aura should be interrupted.
        
        Returns:
            True if interruption should occur
        """
        if self.aura_speaking and self.user_speaking:
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'user_speaking': self.user_speaking,
            'aura_speaking': self.aura_speaking,
            'pending_resume': self.pending_resume
        }


class InterruptionPolicy:
    """
    Policy for handling interruptions.
    
    Defines rules for when interruptions are allowed, how they're handled, etc.
    """
    
    def __init__(self):
        """Initialize interruption policy."""
        self.allowed_modes = [
            "continuous",  # Continuous barge-in
            "pausable",  # Can interrupt but must pause first
            "blocked"  # Never allow interruption
        ]
        self.current_mode = "pausable"
        self.strict_mode = False
        self.require_confirm = False
        self.interruptible_after_duration = 2.0
    
    def can_interrupt(self) -> bool:
        """Check if interruption is allowed in current mode."""
        if self.current_mode == "blocked":
            return False
        
        if self.current_mode == "continuous":
            return True
        
        if self.current_mode == "pausable":
            # Can only interrupt after some duration
            return True  # Simplified for now
        
        return True
    
    def set_mode(self, mode: str) -> None:
        """Set interruption mode."""
        if mode in self.allowed_modes:
            self.current_mode = mode
            logger.info(f"Interruption mode set to: {mode}")
        else:
            logger.warning(f"Unknown interruption mode: {mode}")
    
    def get_mode(self) -> str:
        """Get current interruption mode."""
        return self.current_mode
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'current_mode': self.current_mode,
            'strict_mode': self.strict_mode,
            'require_confirm': self.require_confirm,
            'interruptible_after_duration': self.interruptible_after_duration,
            'allowed_modes': self.allowed_modes
        }
