"""
Device Privacy & Sensitive Window Protection Subsystem
Location: src/desktop/native/security/device_privacy.py

Enforces strict multi-device privacy controls and pre-acquisition blocking for:
1. Microphone streaming and audio recording.
2. Screen capture, window capture, and OCR perception.
3. Camera video streams and photo captures.
4. Sensitive window detection (password managers, security dialogs, BitLocker).

Security Invariants:
- Denied device permission => zero hardware or API capture attempt.
- Sensitive windows (KeePass, BitLocker, Windows Security) trigger capture BLOCK before frame acquisition.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Supported physical/virtual devices requiring privacy governance."""
    MICROPHONE = "microphone"
    SCREEN_CAPTURE = "screen_capture"
    CAMERA = "camera"


class PermissionState(str, Enum):
    """Device permission states."""
    ALLOWED = "allowed"
    DENIED = "denied"
    PROMPT_REQUIRED = "prompt_required"


class SensitiveWindowPolicy(str, Enum):
    """Policy action when sensitive window is detected."""
    BLOCK = "BLOCK"
    REDACT = "REDACT"


# Hard-blocked sensitive window signatures (checked against title, class, and process name)
DEFAULT_SENSITIVE_SIGNATURES: list[dict[str, str]] = [
    {"pattern": "keepass", "type": "substring", "category": "password_manager"},
    {"pattern": "1password", "type": "substring", "category": "password_manager"},
    {"pattern": "bitwarden", "type": "substring", "category": "password_manager"},
    {"pattern": "lastpass", "type": "substring", "category": "password_manager"},
    {"pattern": "dashlane", "type": "substring", "category": "password_manager"},
    {"pattern": "windows security", "type": "substring", "category": "os_security"},
    {"pattern": "credential manager", "type": "substring", "category": "os_security"},
    {"pattern": "bitlocker", "type": "substring", "category": "encryption_keys"},
    {"pattern": "windows hello", "type": "substring", "category": "biometric_auth"},
    {"pattern": "authenticator", "type": "substring", "category": "2fa_mfa"},
    {"pattern": "yubikey", "type": "substring", "category": "hardware_token"},
]


@dataclass
class PrivacyEvaluationResult:
    """Structured decision returned by DevicePrivacyEngine."""
    allowed: bool
    reason: str
    device: DeviceType
    policy: SensitiveWindowPolicy = SensitiveWindowPolicy.BLOCK
    window_metadata: dict[str, Any] = field(default_factory=dict)
    audit_event: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "device": self.device.value,
            "policy": self.policy.value,
            "window_metadata": self.window_metadata,
            "audit_event": self.audit_event,
        }


class SensitiveWindowDetector:
    """
    Evaluates window titles, window classes, process names, and HWNDs against
    sensitive credential and security signatures.
    """

    def __init__(self, signatures: list[dict[str, str]] | None = None) -> None:
        self.signatures = signatures or DEFAULT_SENSITIVE_SIGNATURES

    def evaluate_window(
        self,
        window_title: str = "",
        window_class: str = "",
        process_name: str = "",
        hwnd: int | None = None,
    ) -> tuple[bool, str, str]:
        """
        Check if the targeted or active window matches a sensitive signature.

        Returns:
            (is_sensitive, matched_category, reason)
        """
        candidate_text = f"{window_title} {window_class} {process_name}".lower().strip()
        if not candidate_text:
            return False, "", "Window identity empty or unresolvable."

        for sig in self.signatures:
            pat = sig["pattern"].lower()
            if pat in candidate_text:
                cat = sig.get("category", "sensitive_context")
                reason = (
                    f"Target window matched sensitive signature '{pat}' "
                    f"(Category: {cat}, Title: '{window_title}', Process: '{process_name}')."
                )
                return True, cat, reason

        return False, "", "Window is not flagged as sensitive."


class DevicePrivacyEngine:
    """
    Central thread-safe governance engine managing device capture permissions
    and pre-acquisition sensitive window protection.
    """

    _instance: DevicePrivacyEngine | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._permissions: dict[DeviceType, PermissionState] = {
            DeviceType.MICROPHONE: PermissionState.ALLOWED,
            DeviceType.SCREEN_CAPTURE: PermissionState.ALLOWED,
            DeviceType.CAMERA: PermissionState.DENIED,  # Camera default-denied for privacy
        }
        self._window_detector = SensitiveWindowDetector()
        self._sensitive_window_policy = SensitiveWindowPolicy.BLOCK
        self._state_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> DevicePrivacyEngine:
        """Get or initialize thread-safe singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (used in test teardown)."""
        with cls._lock:
            cls._instance = None

    def set_device_permission(self, device: DeviceType, state: PermissionState) -> None:
        """Explicitly set permission state for a device."""
        with self._state_lock:
            self._permissions[device] = state
            logger.info(f"[DevicePrivacyEngine] Device '{device.value}' permission set to '{state.value}'")

    def get_device_permission(self, device: DeviceType) -> PermissionState:
        """Get current permission state for a device."""
        with self._state_lock:
            return self._permissions.get(device, PermissionState.DENIED)

    def set_sensitive_window_policy(self, policy: SensitiveWindowPolicy) -> None:
        """Configure default action on sensitive windows (BLOCK vs REDACT)."""
        with self._state_lock:
            self._sensitive_window_policy = policy
            logger.info(f"[DevicePrivacyEngine] Sensitive window policy set to '{policy.value}'")

    def evaluate_microphone(self) -> PrivacyEvaluationResult:
        """
        Evaluate whether microphone audio acquisition is permitted.
        Enforces zero-hardware-capture invariant when DENIED.
        """
        with self._state_lock:
            perm = self._permissions.get(DeviceType.MICROPHONE, PermissionState.DENIED)
            if perm != PermissionState.ALLOWED:
                reason = (
                    f"Microphone audio acquisition BLOCKED: permission state is '{perm.value}'. "
                    "Zero audio stream capture allowed."
                )
                logger.warning(f"[DevicePrivacyEngine] {reason}")
                return PrivacyEvaluationResult(
                    allowed=False,
                    reason=reason,
                    device=DeviceType.MICROPHONE,
                    audit_event={"action": "mic_blocked", "permission": perm.value},
                )

            return PrivacyEvaluationResult(
                allowed=True,
                reason="Microphone audio acquisition permitted.",
                device=DeviceType.MICROPHONE,
                audit_event={"action": "mic_allowed", "permission": perm.value},
            )

    def evaluate_camera(self) -> PrivacyEvaluationResult:
        """
        Evaluate whether camera video/image acquisition is permitted.
        """
        with self._state_lock:
            perm = self._permissions.get(DeviceType.CAMERA, PermissionState.DENIED)
            if perm != PermissionState.ALLOWED:
                reason = (
                    f"Camera capture BLOCKED: permission state is '{perm.value}'. "
                    "Zero camera frame acquisition allowed."
                )
                logger.warning(f"[DevicePrivacyEngine] {reason}")
                return PrivacyEvaluationResult(
                    allowed=False,
                    reason=reason,
                    device=DeviceType.CAMERA,
                    audit_event={"action": "camera_blocked", "permission": perm.value},
                )

            return PrivacyEvaluationResult(
                allowed=True,
                reason="Camera acquisition permitted.",
                device=DeviceType.CAMERA,
                audit_event={"action": "camera_allowed", "permission": perm.value},
            )

    def evaluate_screen_capture(
        self,
        window_title: str = "",
        window_class: str = "",
        process_name: str = "",
        hwnd: int | None = None,
    ) -> PrivacyEvaluationResult:
        """
        Evaluate whether screen/window capture is permitted.
        Checks device permission AND performs pre-capture sensitive window inspection.
        """
        with self._state_lock:
            perm = self._permissions.get(DeviceType.SCREEN_CAPTURE, PermissionState.DENIED)
            if perm != PermissionState.ALLOWED:
                reason = (
                    f"Screen capture BLOCKED: device permission state is '{perm.value}'. "
                    "Zero screen frame grab allowed."
                )
                logger.warning(f"[DevicePrivacyEngine] {reason}")
                return PrivacyEvaluationResult(
                    allowed=False,
                    reason=reason,
                    device=DeviceType.SCREEN_CAPTURE,
                    audit_event={"action": "screen_blocked", "permission": perm.value},
                )

            # Pre-capture sensitive window inspection
            is_sens, cat, sens_reason = self._window_detector.evaluate_window(
                window_title=window_title,
                window_class=window_class,
                process_name=process_name,
                hwnd=hwnd,
            )

            if is_sens:
                policy = self._sensitive_window_policy
                reason = (
                    f"Screen capture BLOCKED by SensitiveWindowPolicy ({policy.value}): {sens_reason}"
                )
                logger.warning(f"[DevicePrivacyEngine] {reason}")
                return PrivacyEvaluationResult(
                    allowed=False,
                    reason=reason,
                    device=DeviceType.SCREEN_CAPTURE,
                    policy=policy,
                    window_metadata={
                        "window_title": window_title,
                        "window_class": window_class,
                        "process_name": process_name,
                        "category": cat,
                    },
                    audit_event={
                        "action": "sensitive_window_blocked",
                        "category": cat,
                        "policy": policy.value,
                    },
                )

            return PrivacyEvaluationResult(
                allowed=True,
                reason="Screen capture permitted.",
                device=DeviceType.SCREEN_CAPTURE,
                window_metadata={"window_title": window_title, "process_name": process_name},
                audit_event={"action": "screen_capture_allowed", "permission": perm.value},
            )
