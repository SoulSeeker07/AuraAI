"""
Execution Map — Structured Machine-Readable Action Plan
=======================================================

The DMM produces an ExecutionMap, not free-form instructions.
This fixed schema makes plans deterministic, easy to validate,
and safe for Aura to execute automatically.

Schema:
    Goal: str
    RequiredCapabilities: list[Capability]
    ExecutionPlan: list[ExecutionStep]
    ExpectedResult: str
    Verification: SuccessCriteria
    Fallbacks: list[FallbackOption]
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Capability(str, Enum):
    """Capabilities Aura can delegate to execution engines."""

    DESKTOP = "desktop"
    BROWSER = "browser"
    RESEARCH = "research"
    ENGINEERING = "engineering"
    MEMORY = "memory"
    VOICE = "voice"
    VISION = "vision"
    FILESYSTEM = "filesystem"
    KNOWLEDGE = "knowledge"
    PROVIDER = "provider"
    WORKFLOW = "workflow"
    NONE = "none"


class StepType(str, Enum):
    """Type of execution step."""

    CHECK = "check"
    LAUNCH = "launch"
    NAVIGATE = "navigate"
    EXECUTE = "execute"
    WAIT = "wait"
    VERIFY = "verify"
    GENERATE = "generate"
    SAVE = "save"
    SEARCH = "search"
    READ = "read"
    WRITE = "write"
    CALL = "call"
    ASK = "ask"


@dataclass
class SuccessCriteria:
    """Verification criteria for an execution map."""

    checks: list[str] = field(default_factory=list)
    require_all: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": self.checks,
            "require_all": self.require_all,
        }


@dataclass
class FallbackOption:
    """A fallback strategy if a step fails."""

    trigger: str
    action: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "action": self.action,
            "description": self.description,
        }


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""

    step_type: StepType
    description: str
    capability: Capability = Capability.NONE
    parameters: dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    timeout: int = 30
    parallel: bool = False
    depends_on: list[str] = field(default_factory=list)
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:6]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "description": self.description,
            "capability": self.capability.value,
            "parameters": self.parameters,
            "retries": self.retries,
            "timeout": self.timeout,
            "parallel": self.parallel,
            "depends_on": self.depends_on,
        }


@dataclass
class ExecutionMap:
    """
    The structured output of the DMM.

    This is the ONLY thing the DMM produces. It never executes anything.
    """

    goal: str
    required_capabilities: list[Capability] = field(default_factory=list)
    execution_plan: list[ExecutionStep] = field(default_factory=list)
    expected_result: str = ""
    verification: SuccessCriteria = field(default_factory=SuccessCriteria)
    fallbacks: list[FallbackOption] = field(default_factory=list)
    map_id: str = field(default_factory=lambda: f"map_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Validation ──────────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the execution map against the fixed schema."""
        errors: list[str] = []

        if not self.goal or not self.goal.strip():
            errors.append("ExecutionMap.goal is required")

        if not self.required_capabilities:
            errors.append("ExecutionMap.required_capabilities must not be empty")

        if not self.execution_plan:
            errors.append("ExecutionMap.execution_plan must not be empty")

        if not self.expected_result:
            errors.append("ExecutionMap.expected_result is required")

        if not self.verification.checks:
            errors.append("ExecutionMap.verification.checks must not be empty")

        # Validate each step
        for step in self.execution_plan:
            if not step.description:
                errors.append(f"ExecutionStep {step.step_id} missing description")
            if step.step_type not in StepType:
                errors.append(f"ExecutionStep {step.step_id} has invalid step_type")

        return (len(errors) == 0, errors)

    # ── Serialization ───────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "goal": self.goal,
            "required_capabilities": [c.value for c in self.required_capabilities],
            "execution_plan": [s.to_dict() for s in self.execution_plan],
            "expected_result": self.expected_result,
            "verification": self.verification.to_dict(),
            "fallbacks": [f.to_dict() for f in self.fallbacks],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionMap:
        """Reconstruct an ExecutionMap from a dict."""
        return cls(
            goal=data.get("goal", ""),
            required_capabilities=[
                Capability(c) for c in data.get("required_capabilities", [])
            ],
            execution_plan=[
                ExecutionStep(
                    step_type=StepType(s["step_type"]),
                    description=s["description"],
                    capability=Capability(s.get("capability", "none")),
                    parameters=s.get("parameters", {}),
                    retries=s.get("retries", 0),
                    timeout=s.get("timeout", 30),
                    parallel=s.get("parallel", False),
                    depends_on=s.get("depends_on", []),
                    step_id=s.get("step_id", f"step_{uuid.uuid4().hex[:6]}"),
                )
                for s in data.get("execution_plan", [])
            ],
            expected_result=data.get("expected_result", ""),
            verification=SuccessCriteria(
                checks=data.get("verification", {}).get("checks", []),
                require_all=data.get("verification", {}).get("require_all", True),
            ),
            fallbacks=[
                FallbackOption(
                    trigger=f.get("trigger", ""),
                    action=f.get("action", ""),
                    description=f.get("description", ""),
                )
                for f in data.get("fallbacks", [])
            ],
            map_id=data.get("map_id", f"map_{uuid.uuid4().hex[:8]}"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )

    def log_summary(self) -> str:
        """One-line log representation."""
        return (
            f"[ExecutionMap:{self.map_id}] goal='{self.goal}' "
            f"capabilities={[c.value for c in self.required_capabilities]} "
            f"steps={len(self.execution_plan)}"
        )
