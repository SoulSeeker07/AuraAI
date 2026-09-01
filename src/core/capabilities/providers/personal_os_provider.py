"""
Personal OS Capability Provider
Location: src/core/capabilities/providers/personal_os_provider.py

Exposes governed Personal OS capabilities for daily agenda synthesis,
task management, workspace search, and automated trigger routines.
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class PersonalOSCapabilityProvider(ICapabilityProvider):
    """Capability provider for Personal OS operations."""

    DOMAIN = "personal_os"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {
            c.name: c for c in self._build_capabilities()
        }

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def _build_capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="personal_os.daily_context",
                domain="desktop",
                description="Synthesize prioritized tasks, meetings, and deadlines for today",
                risk_level=ActionRisk.LOW,
                permissions=["personal_os.read"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Target date YYYY-MM-DD"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "daily_context": {"type": "object"},
                    },
                },
            ),
            Capability(
                name="personal_os.search",
                domain="desktop",
                description="Search files and content across the workspace with <1s indexed query",
                risk_level=ActionRisk.LOW,
                permissions=["workspace.read"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                    },
                },
            ),
            Capability(
                name="personal_os.trigger.list",
                domain="desktop",
                description="List all persistent personal routines and triggers",
                risk_level=ActionRisk.LOW,
                permissions=["personal_os.read"],
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            ),
            Capability(
                name="personal_os.trigger.create",
                domain="desktop",
                description="Create a persistent automated routine trigger",
                risk_level=ActionRisk.MEDIUM,
                permissions=["personal_os.manage"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "goal_text": {"type": "string"},
                        "schedule": {"type": "string"},
                        "allowed_capabilities": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "goal_text"],
                },
                output_schema={"type": "object"},
            ),
            Capability(
                name="personal_os.trigger.delete",
                domain="desktop",
                description="Delete a persistent automated routine trigger",
                risk_level=ActionRisk.MEDIUM,
                permissions=["personal_os.manage"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "trigger_id": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
            ),
            Capability(
                name="personal_os.task.add",
                domain="desktop",
                description="Add a task item to personal agenda",
                risk_level=ActionRisk.LOW,
                permissions=["personal_os.manage"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "priority": {"type": "string"},
                        "due_date": {"type": "string"},
                    },
                    "required": ["title"],
                },
                output_schema={"type": "object"},
            ),
            Capability(
                name="personal_os.task.list",
                domain="desktop",
                description="List personal agenda tasks",
                risk_level=ActionRisk.LOW,
                permissions=["personal_os.read"],
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            ),
        ]
