"""
Layer 5: Execution Map Validator
================================

Never trust the LLM blindly.

Every Execution Map must be validated.

Checks:
    * Unknown engines
    * Unknown actions
    * Invalid URLs
    * Dangerous commands
    * Missing verification
    * Invalid JSON

If validation fails → Ask Groq again.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Known Engines and Actions ───────────────────────────────────────────────

_KNOWN_ENGINES = {
    "desktop",
    "browser",
    "research",
    "engineering",
    "memory",
    "voice",
    "vision",
    "filesystem",
    "provider",
}

_KNOWN_ACTIONS = {
    "desktop": {
        "check_running",
        "launch_application",
        "verify_window",
        "close_application",
        "minimize_window",
        "maximize_window",
        "focus_window",
        "get_clipboard",
        "set_clipboard",
    },
    "browser": {
        "navigate",
        "verify",
        "open_tab",
        "close_tab",
        "switch_tab",
        "get_tabs",
        "search",
    },
    "research": {
        "search",
        "verify_results",
        "get_sources",
    },
    "engineering": {
        "execute",
        "verify",
        "inspect",
    },
    "memory": {
        "search",
        "remember",
        "read_session_history",
        "forget",
    },
    "voice": {
        "speak",
        "listen",
        "set_volume",
    },
    "vision": {
        "analyze_image",
        "ocr",
    },
    "filesystem": {
        "inspect_workspace",
        "read_file",
        "write_file",
        "list_files",
        "create_directory",
    },
    "provider": {
        "chat",
        "synthesize",
        "summarize",
        "generate",
    },
}

# ── Dangerous Patterns ──────────────────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"format\s+[a-z]:",
    r"del\s+/[sfq]",
    r"shutdown\s+[^a-z]",
    r"taskkill\s+/f",
    r"reg\s+delete",
    r"diskpart",
    r"mkfs",
    r"dd\s+if=",
]


@dataclass
class ValidationResult:
    """The result of validating an Execution Map."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ExecutionMapValidator:
    """
    Validates Execution Maps before they are executed.

    Never trust the LLM blindly.
    """

    def validate(self, execution_map: dict[str, Any]) -> ValidationResult:
        """
        Validate an Execution Map.

        Args:
            execution_map: The Execution Map dict to validate.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # ── 1. Basic structure ──────────────────────────────────────────────
        if not isinstance(execution_map, dict):
            return ValidationResult(valid=False, errors=["Execution Map is not a dict"])

        if not execution_map.get("goal"):
            errors.append("Execution Map missing 'goal'")

        capabilities = execution_map.get("capabilities", [])
        if not isinstance(capabilities, list) or not capabilities:
            errors.append("Execution Map missing 'capabilities'")

        steps = execution_map.get("steps", [])
        if not isinstance(steps, list) or not steps:
            errors.append("Execution Map missing 'steps'")

        verification = execution_map.get("verification", [])
        if not isinstance(verification, list) or not verification:
            errors.append("Execution Map missing 'verification'")

        # ── 2. Validate capabilities ────────────────────────────────────────
        for cap in capabilities:
            if cap not in _KNOWN_ENGINES:
                errors.append(f"Unknown capability/engine: '{cap}'")

        # ── 3. Validate steps ───────────────────────────────────────────────
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i} is not a dict")
                continue

            engine = step.get("engine", "")
            action = step.get("action", "")

            if engine not in _KNOWN_ENGINES:
                errors.append(f"Step {i}: unknown engine '{engine}'")
                continue

            if action not in _KNOWN_ACTIONS.get(engine, set()):
                errors.append(
                    f"Step {i}: unknown action '{action}' for engine '{engine}'"
                )

            # Validate URL parameters
            params = step.get("parameters", {})
            if isinstance(params, dict):
                url = params.get("url", "")
                if url and not self._is_valid_url(url):
                    errors.append(f"Step {i}: invalid URL '{url}'")

                # Check for dangerous commands
                command = params.get("command", "")
                if command and self._is_dangerous(command):
                    errors.append(f"Step {i}: dangerous command detected")

        # ── 4. Validate fallbacks ───────────────────────────────────────────
        fallbacks = execution_map.get("fallbacks", [])
        if isinstance(fallbacks, list):
            for i, fb in enumerate(fallbacks):
                if not isinstance(fb, dict):
                    errors.append(f"Fallback {i} is not a dict")
                    continue
                if not fb.get("trigger"):
                    errors.append(f"Fallback {i}: missing 'trigger'")
                if not fb.get("action"):
                    errors.append(f"Fallback {i}: missing 'action'")

        # ── 5. Warnings ─────────────────────────────────────────────────────
        if len(steps) > 10:
            warnings.append(
                f"Execution Map has {len(steps)} steps — consider simplifying"
            )

        if not fallbacks:
            warnings.append("Execution Map has no fallbacks")

        valid = len(errors) == 0

        if valid:
            logger.info("Execution Map validation PASSED")
        else:
            logger.warning(f"Execution Map validation FAILED: {errors}")

        return ValidationResult(valid=valid, errors=errors, warnings=warnings)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if a URL is valid."""
        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return bool(re.match(pattern, url))

    @staticmethod
    def _is_dangerous(command: str) -> bool:
        """Check if a command contains dangerous patterns."""
        command_lower = command.lower()
        return any(re.search(pattern, command_lower) for pattern in _DANGEROUS_PATTERNS)


__all__ = ["ExecutionMapValidator", "ValidationResult"]
