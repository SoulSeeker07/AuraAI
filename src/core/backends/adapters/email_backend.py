"""
Email Backend Adapter
Location: src/core/backends/adapters/email_backend.py

Connects MasterOrchestrator to EmailPlugin for sending and querying emails.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class EmailBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for email operations.
    """

    @property
    def name(self) -> str:
        return "Email Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "email",
            "email.send",
            "email.read_inbox",
            "email.search",
            "email.reply",
            "email.forward",
            "email.list_folders",
            "email.move",
            "email.delete",
            "email.get_attachments",
            "email.draft",
            "mail",
            "send_email",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 300.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        from plugins.email.email_plugin import EmailPlugin

        plugin = EmailPlugin()
        plugin.load()
        plugin.initialize()

        args = arguments or {}
        res = plugin.execute(capability=capability, **args)

        return ExecutionResult(
            success=True if not isinstance(res, dict) or res.get("status") != "error" else False,
            planner="email",
            goal=goal,
            observations=[f"Email operation completed: {capability}"],
            data={"result": res},
        )
