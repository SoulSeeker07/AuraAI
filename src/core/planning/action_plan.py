"""
ActionPlan — Structured Desktop Action Contract
Location: src/core/planning/action_plan.py

Every backend receives one ActionPlan instead of three loose primitives.
This enables replay, explainability, structured logging, and typed backend contracts.

Pipeline position:
    SubTask (TaskDecomposer)
      ↓
    PolicyDecision (ExecutionPolicy)
      ↓
    ActionPlan  ← this module
      ↓
    Backend.execute_plan(plan)
      ↓
    Windows API + Verification

Example:
    {
      "action":        "app_open",
      "target":        "notepad",
      "goal":          "Open Notepad",
      "capability":    "app_open",
      "reuse_existing": false,
      "verify":        true,
      "ownership":     "aura",
      "policy_action": "launch_new",
      "arguments":     {"app_name": "notepad"},
      "session_id":    "sess_abc123",
      "plan_id":       "plan_7f2e",
      "created_at":    "2026-08-06T01:30:00",
      "metadata":      {}
    }
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ActionPlan:
    """
    Typed, replayable, loggable action contract sent to every backend.

    Fields
    ------
    action       : Semantic verb — "app_open", "app_close", "window.minimize", ...
    target       : The resource name — "notepad", "chrome", "instagram_tab"
    goal         : Original human goal text for log context
    capability   : Backend capability string (maps to BackendRegistry routing)
    reuse_existing : ExecutionPolicy said REUSE_EXISTING
    verify       : Require OS-level verification after execution
    ownership    : "aura" | "user" | "shared"
    policy_action: Raw PolicyAction value string for explainability
    arguments    : Passthrough arguments for backend.execute()
    session_id   : Parent AgentSession ID for traceability
    plan_id      : Unique plan UUID for replay / log correlation
    created_at   : ISO timestamp when plan was built
    metadata     : Extra typed context — hwnd, pid, tab_id, confirmation_key, ...
    """

    action: str
    target: str
    goal: str
    capability: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reuse_existing: bool = False
    verify: bool = True
    ownership: str = "aura"
    policy_action: str = "launch_new"
    session_id: str = ""
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ─────────────────────────────────────────────────────

    @classmethod
    def for_desktop(
        cls,
        action: str,
        target: str,
        goal: str,
        *,
        capability: str | None = None,
        arguments: dict[str, Any] | None = None,
        reuse_existing: bool = False,
        policy_action: str = "launch_new",
        session_id: str = "",
        hwnd: int | None = None,
        pid: int | None = None,
        window_count: int = 0,
    ) -> ActionPlan:
        """
        Convenience factory for desktop/window actions.
        Automatically sets capability from action if not provided.
        """
        cap = capability or action
        meta: dict[str, Any] = {}
        if hwnd is not None:
            meta["hwnd"] = hwnd
        if pid is not None:
            meta["pid"] = pid
        if window_count:
            meta["window_count"] = window_count

        args = arguments or {}
        if "app_name" not in args:
            args["app_name"] = target

        return cls(
            action=action,
            target=target,
            goal=goal,
            capability=cap,
            arguments=args,
            reuse_existing=reuse_existing,
            verify=True,
            ownership="aura",
            policy_action=policy_action,
            session_id=session_id,
            metadata=meta,
        )

    @classmethod
    def from_subtask(
        cls,
        subtask: Any,  # SubTask — avoid circular import
        policy_action: str = "launch_new",
        reuse_existing: bool = False,
        session_id: str = "",
        hwnd: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> ActionPlan:
        """Build an ActionPlan directly from a TaskDecomposer SubTask.

        Content propagation: if the subtask declares ``input_artifacts``,
        we look them up in the session's artifact store and pull their
        payload into ``params["content"]`` and ``params["file_path"]``.
        This replaces the old approach of scraping raw observations.
        """
        params = dict(subtask.parameters or {})

        # Pull content and file paths from the artifact store
        if context and getattr(subtask, "input_artifacts", None):
            session = context.get("session")
            if session and hasattr(session, "get_artifact"):
                for art_id in subtask.input_artifacts:
                    art = session.get_artifact(art_id)
                    if art is not None:
                        # Propagate content payload
                        if art.has_payload and "content" not in params:
                            params["content"] = art.content
                        if "artifact" not in params:
                            params["artifact"] = art
                        # Propagate file location
                        if art.location and "file_path" not in params:
                            params["file_path"] = art.location
                            params["target_file"] = art.location

        target = (
            params.get("app_name")
            or params.get("target")
            or subtask.description.split()[-1]
        )
        return cls.for_desktop(
            action=subtask.capability,
            target=str(target).lower().strip(),
            goal=subtask.description,
            capability=subtask.capability,
            arguments=params,
            reuse_existing=reuse_existing,
            policy_action=policy_action,
            session_id=session_id,
            hwnd=hwnd,
        )

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "action": self.action,
            "target": self.target,
            "goal": self.goal,
            "capability": self.capability,
            "reuse_existing": self.reuse_existing,
            "verify": self.verify,
            "ownership": self.ownership,
            "policy_action": self.policy_action,
            "arguments": self.arguments,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def log_summary(self) -> str:
        """One-line log representation."""
        reuse_flag = " [REUSE]" if self.reuse_existing else ""
        meta_str = ""
        if self.metadata.get("hwnd"):
            meta_str += f" hwnd={self.metadata['hwnd']}"
        if self.metadata.get("pid"):
            meta_str += f" pid={self.metadata['pid']}"
        return (
            f"[ActionPlan:{self.plan_id}] "
            f"action={self.action} target={self.target} "
            f"policy={self.policy_action}{reuse_flag} "
            f"verify={self.verify}{meta_str}"
        )
