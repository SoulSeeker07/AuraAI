"""
Terminal Backend Adapter
Location: src/core/backends/adapters/terminal_backend.py

Connects MasterOrchestrator to TerminalManager using lazy resolution to satisfy
the architectural layer import contract (core cannot import desktop top-level).
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class TerminalBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for shell / terminal command execution.
    """

    @property
    def name(self) -> str:
        return "Terminal Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "terminal",
            "terminal.execute",
            "terminal.execute_async",
            "terminal.send_input",
            "terminal.kill_session",
            "terminal.get_output",
            "terminal.list_sessions",
            "terminal.get_cwd",
            "terminal.set_cwd",
            "terminal.get_env",
            "terminal.set_env",
            "shell",
            "run_command",
            "command",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 100.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def _format_observation(self, capability: str, data: dict[str, Any], error: str | None) -> str:
        if error:
            return f"Terminal error: {error}"

        cap = capability.lower()
        if cap == "terminal.get_cwd":
            return f"Current working directory: {data.get('cwd', '')}"
        elif cap == "terminal.set_cwd":
            return f"Changed working directory to: {data.get('cwd', '')}"
        elif cap == "terminal.get_env":
            if "value" in data:
                return f"Environment variable '{data.get('key')}': {data.get('value')}"
            return f"Retrieved {len(data.get('env', {}))} environment variables."
        elif cap == "terminal.set_env":
            return f"Set environment variable '{data.get('key')}' = '{data.get('value')}'"
        elif cap == "terminal.list_sessions":
            sessions = data.get("sessions", [])
            return f"Active terminal sessions ({len(sessions)}): {sessions}"
        elif cap == "terminal.execute_async":
            return f"Started background session '{data.get('session_id')}' for command: {data.get('command')}"
        elif cap == "terminal.get_output":
            return f"Session '{data.get('session_id')}' output (running={data.get('is_running')}):\n{data.get('output', '')}"
        elif cap == "terminal.kill_session":
            return f"Terminated background session '{data.get('session_id')}'"
        elif "stdout" in data:
            cmd = data.get("command", "")
            code = data.get("exit_code", 0)
            stdout = data.get("stdout", "")
            stderr = data.get("stderr", "")
            obs = f"Command '{cmd}' completed with exit code {code}."
            if stdout:
                obs += f"\nStdout:\n{stdout}"
            if stderr:
                obs += f"\nStderr:\n{stderr}"
            return obs
        else:
            return f"Terminal action '{capability}' executed successfully."

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        # Lazy import to obey layer import contracts
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry

        registry = NativeManagerRegistry.get_instance()
        term_mgr = registry.get_manager("terminal")

        if not term_mgr:
            registry.discover()
            term_mgr = registry.get_manager("terminal")

        if not term_mgr:
            return ExecutionResult(
                success=False,
                planner="terminal",
                goal=goal,
                warnings=["TerminalManager could not be loaded from native layer."],
            )

        res = term_mgr.execute(capability=capability, goal=goal, arguments=arguments)
        observation = self._format_observation(capability, res.data, res.error)

        return ExecutionResult(
            success=res.success,
            planner="terminal",
            goal=goal,
            observations=[observation],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

