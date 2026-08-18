"""
Office Backend Adapter
Location: src/core/backends/adapters/office_backend.py

Connects MasterOrchestrator to OfficePlugin for document generation, spreadsheets, and printing.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class OfficeBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for office document and spreadsheet manipulation.
    """

    @property
    def name(self) -> str:
        return "Office Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "office",
            "office.create_document",
            "office.read_document",
            "office.edit_document",
            "office.convert",
            "office.merge_pdfs",
            "office.extract_text",
            "office.create_spreadsheet",
            "office.read_spreadsheet",
            "office.create_presentation",
            "office.print",
            "document",
            "spreadsheet",
            "excel",
            "word",
            "pdf",
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

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        from plugins.office.office_plugin import OfficePlugin

        plugin = OfficePlugin()
        plugin.load()
        plugin.initialize()

        args = arguments or {}
        res = plugin.execute(capability=capability, **args)

        return ExecutionResult(
            success=True if not isinstance(res, dict) or res.get("status") != "error" else False,
            planner="office",
            goal=goal,
            observations=[f"Office operation: {capability}"],
            data={"result": res},
        )
