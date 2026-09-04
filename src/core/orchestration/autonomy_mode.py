"""
M19.2 Autonomy Mode & Risk Classification
=========================================
Location: src/core/orchestration/autonomy_mode.py

Defines system autonomy levels (ASK, ASSISTED, AUTONOMOUS) and deterministic action risk classification.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SAFE_SANDBOX_PATTERNS = (
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".cache",
    ".coverage",
)


def is_safe_sandbox_path(path: str | Path | list[Any] | None) -> bool:
    """
    Determine whether a target path resides strictly within a safe, disposable sandbox directory
    (e.g., system temp folders, pytest caches, __pycache__, temporary runtime logs/screenshots).
    """
    if not path:
        return False

    if isinstance(path, (list, tuple, set)):
        return len(path) > 0 and all(is_safe_sandbox_path(p) for p in path)

    try:
        p = Path(str(path)).resolve()
        p_str = str(p).lower()

        # 1. System/OS Temp Directories
        temp_dirs = [tempfile.gettempdir().lower()]
        for env_var in ("TEMP", "TMP", "TMPDIR"):
            val = os.environ.get(env_var)
            if val:
                temp_dirs.append(str(Path(val).resolve()).lower())

        for t_dir in temp_dirs:
            if p_str.startswith(t_dir):
                return True

        if "appdata\\local\\temp" in p_str or "appdata/local/temp" in p_str:
            return True

        # 2. Known Safe Disposable Sandbox Cache Folders in Path Parts
        parts = [part.lower() for part in p.parts]
        for pattern in SAFE_SANDBOX_PATTERNS:
            if pattern in parts or pattern in p_str:
                return True

        # 3. Project runtime temporary files / screenshots / logs / scratch
        if ("data\\runtime" in p_str or "data/runtime" in p_str) and (
            "temp" in p_str or "screenshots" in p_str or "scratch" in p_str
        ):
            return True

        # 4. Old logs in log directories if aged or temporary
        if ("logs" in parts or "log" in parts) and p.suffix in (".log", ".tmp", ".bak"):
            if p.exists() and p.is_file():
                import time

                age_days = (time.time() - p.stat().st_mtime) / 86400
                if age_days >= 7:
                    return True
            elif "temp" in p_str or "cache" in p_str:
                return True

    except Exception as e:
        logger.debug(f"[is_safe_sandbox_path] Path inspection failed for '{path}': {e}")
        return False

    return False


def _extract_target_paths(params: dict[str, Any] | None) -> list[str]:
    if not params:
        return []
    target_paths: list[str] = []
    for key in ("path", "target", "file_path", "target_path", "target_file", "dir_path", "directory"):
        val = params.get(key)
        if val and isinstance(val, (str, Path)):
            target_paths.append(str(val))
    for key in ("paths", "files", "targets"):
        val = params.get(key)
        if val and isinstance(val, (list, tuple, set)):
            target_paths.extend([str(item) for item in val if item])
    return target_paths


class AutonomyLevel(str, Enum):
    """System-wide autonomy operating mode."""

    ASK = "ask"                # Confirm all actions before execution
    ASSISTED = "assisted"      # Execute low/medium risk actions; confirm high/critical risk (DEFAULT)
    AUTONOMOUS = "autonomous"  # Execute within granted boundaries; confirm critical risk only


class ActionRisk(str, Enum):
    """Risk severity classification of an execution action."""

    LOW = "low"            # Non-mutating or safe read-only operations
    MEDIUM = "medium"      # Standard creation, edit, or local UI navigation
    HIGH = "high"          # Destructive file actions, bulk edits, messaging, external state changes
    CRITICAL = "critical"  # Purchases, financial checkout, credential submission, key destruction


def classify_action_risk(engine: str, action: str, params: dict[str, Any] | None = None) -> ActionRisk:
    """
    Classify the risk level of an intended engine action deterministically.

    Args:
        engine: Target engine (desktop, browser, engineering, etc.).
        action: Specific action name (e.g., "file.delete", "checkout").
        params: Optional execution parameters.

    Returns:
        ActionRisk enum value.
    """
    action_lower = (action or "").lower()
    engine_lower = (engine or "").lower()
    params = params or {}

    # Check CapabilityRegistry authoritative declaration first
    try:
        from core.capabilities.capability_registry import CapabilityRegistry
        cap = CapabilityRegistry.get_instance().get(action)
        if cap is not None:
            if cap.risk_level == ActionRisk.CRITICAL:
                return ActionRisk.CRITICAL
            if cap.risk_level == ActionRisk.HIGH or cap.requires_confirmation or getattr(cap, "is_destructive", False):
                # Allow Scoped Sandbox Auto-Approval for safe disposable paths
                if action_lower in ("file.delete", "file.remove", "directory.delete"):
                    extracted_paths = _extract_target_paths(params)
                    if extracted_paths and all(is_safe_sandbox_path(p) for p in extracted_paths):
                        return ActionRisk.LOW
                return ActionRisk.HIGH
            return cap.risk_level
        elif "." in action:
            logger.debug(
                f"[classify_action_risk] Capability '{action}' not registered in CapabilityRegistry; using heuristic classification."
            )
    except (ImportError, AttributeError) as err:
        logger.warning(
            f"[classify_action_risk] Failed to import/query CapabilityRegistry for '{action}': {err}. Using heuristic fallback."
        )
    except Exception as err:
        logger.warning(
            f"[classify_action_risk] Unexpected error querying CapabilityRegistry for '{action}': {err}. Using heuristic fallback."
        )

    # 1. Critical Risk Operations (Financial, destructive auth, credential leaks)
    critical_keywords = [
        "checkout", "purchase", "pay", "buy", "credential", "password",
        "secret", "private_key", "shopping.checkout", "order.place"
    ]
    if any(kw in action_lower for kw in critical_keywords) or any(kw in str(params).lower() for kw in critical_keywords):
        return ActionRisk.CRITICAL

    # 2. High Risk Operations (Destructive mutations, form submissions, external posts)
    high_keywords = [
        "delete", "remove", "drop", "truncate", "clear", "kill", "unlink",
        "bulk_delete", "send_message", "send_email", "post", "publish",
        "rmdir", "destroy", "format", "submit", "form.submit", "form.fill"
    ]
    if any(kw in action_lower for kw in high_keywords):
        # Allow Scoped Sandbox Auto-Approval for safe paths
        if action_lower in ("file.delete", "file.remove", "directory.delete", "delete", "remove", "clear", "unlink"):
            extracted_paths = _extract_target_paths(params)
            if extracted_paths and all(is_safe_sandbox_path(p) for p in extracted_paths):
                return ActionRisk.LOW
        return ActionRisk.HIGH

    # 2b. High-risk phrasing embedded in the execution parameters
    params_text = str(params).lower()
    high_risk_phrase_patterns = [
        r"\bformat\b.*\b(?:drive|disk|volume|partition|usb|flash|media)\b",
        r"\b(?:wipe|erase|purge)\b.*\b(?:all|everything|entire|drive|disk)\b",
        r"\bkill\b.*\b(?:all|every|process|processes|task|tasks|service|services)\b",
        r"\b(?:delete|remove|drop|destroy)\b.*\b(?:all|everything|every|entire)\b",
        r"\b(?:shutdown|reboot|halt)\b.*\b(?:all|everything|now|processes|services)\b",
        r"\b(?:logout|sign\s*out|signout)\b.*\b(?:all|every|now|sessions?)\b",
        r"\brm\s+-\s*rf\b",
    ]
    if any(re.search(pat, params_text) for pat in high_risk_phrase_patterns):
        return ActionRisk.HIGH

    # Check file modification risk
    if action_lower in ("file.delete", "file.remove", "directory.delete"):
        extracted_paths = _extract_target_paths(params)
        if extracted_paths and all(is_safe_sandbox_path(p) for p in extracted_paths):
            return ActionRisk.LOW
        return ActionRisk.HIGH

    # 3. Medium Risk Operations (State mutations, cross-app transfers, uploads)
    medium_keywords = [
        "edit", "update", "modify", "write", "create", "launch", "open_app",
        "click", "input_text", "shopping.cart.add", "cart.add", "cart",
        "transfer", "upload", "transfer_to", "file.upload", "cross_app", "transfer.cross_app"
    ]
    if any(kw in action_lower for kw in medium_keywords):
        return ActionRisk.MEDIUM

    # 4. Default Low Risk Operations (Reads, Searches, Observations)
    return ActionRisk.LOW


def should_require_confirmation(level: AutonomyLevel | str, risk: ActionRisk | str) -> bool:
    """
    Determine if user confirmation is required based on autonomy level and action risk.

    Args:
        level: Current system AutonomyLevel.
        risk: ActionRisk of the intended operation.

    Returns:
        True if user confirmation prompt is required before execution; False otherwise.
    """
    if isinstance(level, str):
        level = AutonomyLevel(level.lower())
    if isinstance(risk, str):
        risk = ActionRisk(risk.lower())

    if level == AutonomyLevel.ASK:
        return True

    if level == AutonomyLevel.ASSISTED:
        return risk in (ActionRisk.HIGH, ActionRisk.CRITICAL)

    if level == AutonomyLevel.AUTONOMOUS:
        return risk == ActionRisk.CRITICAL

    return True


__all__ = [
    "AutonomyLevel",
    "ActionRisk",
    "classify_action_risk",
    "should_require_confirmation",
    "is_safe_sandbox_path",
]
