"""
Observation & Verification Models
Location: src/core/orchestration/observation_models.py

Defines standardized data models for engine state observations, expected state targets,
and evidence-backed verification reports for Milestone 18.
"""

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureType(str, Enum):
    """Classification of step, pipeline, and goal failures."""

    NONE = "none"
    EXECUTION_FAILURE = "execution_failure"      # Engine failed to execute action (e.g. process crash)
    VERIFICATION_FAILURE = "verification_failure"  # Action completed, but observed state did not match expected state
    GOAL_FAILURE = "goal_failure"                # Steps executed, but user goal was not achieved
    ELEMENT_NOT_FOUND = "element_not_found"      # UI/DOM selector or element not present
    STATE_MISMATCH = "state_mismatch"            # Observed state differs from required goal state
    GOAL_UNFULFILLED = "goal_unfulfilled"        # Interaction completed without end-to-end goal evidence
    TIMEOUT = "timeout"                          # Operation timed out before state verification


@dataclass
class Observation:
    """Standardized engine observation evidence."""

    engine: str  # e.g., "desktop", "browser", "engineering"
    action_id: str
    state: str   # e.g., "window_visible", "page_loaded", "search_results"
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "deterministic"  # "deterministic", "dom", "ui_automation", "screenshot", "vision"
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "action_id": self.action_id,
            "state": self.state,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "source": self.source,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


@dataclass
class ExpectedState:
    """Extensible expected target state for step verification."""

    process: str | None = None
    window: str | None = None
    url: str | None = None
    http_status: int | None = None
    dom: dict[str, Any] = field(default_factory=dict)
    accessibility: dict[str, Any] = field(default_factory=dict)
    element: str | None = None
    screenshot_conditions: dict[str, Any] = field(default_factory=dict)
    browser_state: str | None = None
    custom_conditions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "process": self.process,
            "window": self.window,
            "url": self.url,
            "http_status": self.http_status,
            "dom": self.dom,
            "accessibility": self.accessibility,
            "element": self.element,
            "screenshot_conditions": self.screenshot_conditions,
            "browser_state": self.browser_state,
            "custom_conditions": self.custom_conditions,
        }


@dataclass
class VerificationReport:
    """Evidence-backed verification report produced post-observation."""

    passed: bool
    expected_state: ExpectedState
    observation: Observation
    checks: dict[str, bool] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0
    failure_type: FailureType = FailureType.NONE
    timestamp: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "expected_state": self.expected_state.to_dict(),
            "observation": self.observation.to_dict(),
            "checks": self.checks,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "failure_type": self.failure_type.value if isinstance(self.failure_type, Enum) else str(self.failure_type),
            "timestamp": self.timestamp,
        }
