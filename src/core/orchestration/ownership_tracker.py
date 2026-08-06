"""
Resource Ownership Tracker
Location: src/core/orchestration/ownership_tracker.py

Tracks ownership of OS resources (windows, browser tabs, processes, files, terminals)
to distinguish between resources spawned by Aura AI (ResourceOwner.AURA) versus
resources opened independently by the user (ResourceOwner.USER).

Enables targeted commands like 'Close everything you opened' without touching user resources.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ResourceOwner(str, Enum):
    """Enumeration of resource owners."""

    AURA = "aura"  # Created/opened by Aura AI
    USER = "user"  # Created/opened independently by User
    SHARED = "shared"  # Shared resource (e.g. system services)


@dataclass
class TrackedResource:
    """Represents a tracked system resource with rich creation metadata."""

    resource_id: str
    resource_type: str  # "tab", "window", "process", "file", "terminal"
    owner: ResourceOwner = ResourceOwner.AURA
    goal: str = ""
    planner: str = ""
    backend: str = ""
    reason: str = ""
    session_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "owner": self.owner.value,
            "goal": self.goal,
            "planner": self.planner,
            "backend": self.backend,
            "reason": self.reason,
            "session_id": self.session_id,
            "details": self.details,
            "created_at": self.created_at,
        }


class ResourceOwnershipTracker:
    """
    Central registry for tracking resource ownership across Aura AI.
    """

    _instance: ResourceOwnershipTracker | None = None

    def __init__(self):
        self._resources: dict[str, TrackedResource] = {}
        self._logger = logging.getLogger(__name__)

    @classmethod
    def get_instance(cls) -> ResourceOwnershipTracker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register_resource(
        self,
        resource_type: str,
        resource_id: str,
        owner: ResourceOwner = ResourceOwner.AURA,
        details: dict[str, Any] | None = None,
    ) -> TrackedResource:
        """
        Register a new tracked resource with an owner.
        """
        key = f"{resource_type}:{resource_id}"
        resource = TrackedResource(
            resource_id=resource_id,
            resource_type=resource_type,
            owner=owner,
            details=details or {},
        )
        self._resources[key] = resource
        self._logger.info(
            f"Registered resource [{resource_type}] '{resource_id}' owned by '{owner.value}'"
        )
        return resource

    def is_aura_owned(self, resource_type: str, resource_id: str) -> bool:
        """Check if a specific resource was spawned by Aura."""
        key = f"{resource_type}:{resource_id}"
        if key in self._resources:
            return self._resources[key].owner == ResourceOwner.AURA
        return False

    def get_owner(self, resource_type: str, resource_id: str) -> ResourceOwner:
        """Get the owner of a resource. Defaults to USER for untracked pre-existing items."""
        key = f"{resource_type}:{resource_id}"
        if key in self._resources:
            return self._resources[key].owner
        return ResourceOwner.USER

    def get_aura_resources(
        self, resource_type: str | None = None
    ) -> list[TrackedResource]:
        """Get all resources owned by Aura AI."""
        res: list[TrackedResource] = []
        for r in self._resources.values():
            if r.owner == ResourceOwner.AURA:
                if resource_type is None or r.resource_type == resource_type:
                    res.append(r)
        return res

    def get_user_resources(
        self, resource_type: str | None = None
    ) -> list[TrackedResource]:
        """Get all resources owned by the user."""
        res: list[TrackedResource] = []
        for r in self._resources.values():
            if r.owner == ResourceOwner.USER:
                if resource_type is None or r.resource_type == resource_type:
                    res.append(r)
        return res

    def clear(self) -> None:
        """Clear tracked resources."""
        self._resources.clear()
