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
        try:
            from plugins.email.email_plugin import EmailPlugin
        except ImportError:
            import sys
            from pathlib import Path
            root = Path(__file__).resolve().parents[4]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            import plugins
            root_plugins = str(root / "plugins")
            if hasattr(plugins, "__path__") and root_plugins not in plugins.__path__:
                plugins.__path__.append(root_plugins)
            from plugins.email.email_plugin import EmailPlugin

        plugin = EmailPlugin()
        plugin.load()
        plugin.initialize()

        args = arguments or {}
        res = plugin.execute(capability=capability, **args)

        is_error = False
        err_msg = ""
        if isinstance(res, dict) and (res.get("status") in ("error", "mock_sent") or "error_code" in res):
            is_error = True
            err_msg = res.get("message") or f"Email operation failed: {res.get('error_code', 'UNKNOWN_ERROR')}"
        elif isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict) and (res[0].get("status") == "error" or "error_code" in res[0]):
            is_error = True
            err_msg = res[0].get("message") or f"Email operation failed: {res[0].get('error_code', 'UNKNOWN_ERROR')}"

        if is_error:
            return ExecutionResult(
                success=False,
                planner="email",
                goal=goal,
                error=err_msg,
                observations=[f"[ERROR] Email operation failed: {err_msg}"],
                data={"result": res},
            )

        return ExecutionResult(
            success=True,
            planner="email",
            goal=goal,
            observations=[f"[OK] Email operation completed: {capability}"],
            data={"result": res},
        )
