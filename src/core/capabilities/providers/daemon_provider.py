"""
Daemon & Background Operations Capability Provider
Location: src/core/capabilities/providers/daemon_provider.py

Exposes governed capabilities for background task execution, scheduling,
cancellation, and status tracking.
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class DaemonCapabilityProvider(ICapabilityProvider):
    """Capability provider exposing background daemon and scheduling capabilities."""

    DOMAIN = "daemon"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {c.name: c for c in self._build_capabilities()}

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
                name="daemon.spawn",
                domain="daemon",
                description="Spawn an asynchronous background task in the daemon runtime",
                risk_level=ActionRisk.LOW,
                permissions=["daemon.execute"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "capability": {"type": "string"},
                        "goal": {"type": "string"},
                        "parameters": {"type": "object"},
                        "autonomy_token": {"type": "string"},
                    },
                    "required": ["capability", "goal"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "run_id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
            ),
            Capability(
                name="daemon.status",
                domain="daemon",
                description="Query the execution status of a background job or run",
                risk_level=ActionRisk.LOW,
                permissions=["daemon.read"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "run_id": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "status": {"type": "string"},
                        "result": {"type": "object"},
                    },
                },
            ),
            Capability(
                name="daemon.list",
                domain="daemon",
                description="List all active and scheduled daemon jobs",
                risk_level=ActionRisk.LOW,
                permissions=["daemon.read"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "include_cancelled": {"type": "boolean"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "jobs": {"type": "array"},
                    },
                },
            ),
            Capability(
                name="daemon.pause",
                domain="daemon",
                description="Pause a scheduled daemon job",
                risk_level=ActionRisk.MEDIUM,
                permissions=["daemon.manage"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                output_schema={"type": "object"},
            ),
            Capability(
                name="daemon.resume",
                domain="daemon",
                description="Resume a paused daemon job",
                risk_level=ActionRisk.MEDIUM,
                permissions=["daemon.manage"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                output_schema={"type": "object"},
            ),
            Capability(
                name="daemon.cancel",
                domain="daemon",
                description="Cancel a background job or active run",
                risk_level=ActionRisk.MEDIUM,
                permissions=["daemon.manage"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                output_schema={"type": "object"},
            ),
        ]
