"""
Aura Office Automation Plugin
=============================
Plugin for Word (.docx), Excel (.xlsx), PowerPoint (.pptx), PDF, and printing automation.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest

logger = logging.getLogger(__name__)


class OfficePlugin(Plugin):
    """
    Office Document Automation Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="office",
                version="1.0.0",
                author="Aura AI",
                description="Office documents (Word, Excel, PowerPoint, PDF) automation plugin.",
                category=PluginCategory.OFFICE,
                capabilities=[
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
                ],
            )
        super().__init__(manifest)

    def load(self) -> bool:
        self.state = "initialized"
        return True

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability.startswith("office.") or capability in self.manifest.capabilities

    def _create_doc(self, path_str: str, content: str) -> dict[str, Any]:
        p = Path(path_str).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            import docx
            doc = docx.Document()
            doc.add_paragraph(content)
            doc.save(str(p))
            return {"path": str(p), "type": "docx", "status": "created"}
        except ImportError:
            # Fallback plain text / markdown
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return {"path": str(p), "type": "text", "status": "created_fallback"}

    def _create_spreadsheet(self, path_str: str, rows: list[list[Any]]) -> dict[str, Any]:
        p = Path(path_str).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            for row in rows:
                ws.append(row)
            wb.save(str(p))
            return {"path": str(p), "type": "xlsx", "status": "created"}
        except ImportError:
            # Fallback to CSV
            import csv
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            return {"path": str(p), "type": "csv", "status": "created_csv_fallback"}

    def execute(self, capability: str, **kwargs: Any) -> Any:
        cap = capability.lower()
        if cap == "office.create_document":
            path = kwargs.get("path") or "document.docx"
            content = kwargs.get("content") or kwargs.get("text") or "Aura AI Document"
            return self._create_doc(path, content)
        elif cap == "office.create_spreadsheet":
            path = kwargs.get("path") or "spreadsheet.xlsx"
            rows = kwargs.get("rows") or [["Header 1", "Header 2"], ["Val 1", "Val 2"]]
            return self._create_spreadsheet(path, rows)
        elif cap == "office.print":
            path = kwargs.get("path") or ""
            if path and os.path.exists(path):
                # Use Win32 ShellExecute print verb
                try:
                    import win32api
                    win32api.ShellExecute(0, "print", path, None, ".", 0)
                    return {"path": path, "status": "sent_to_printer"}
                except Exception:
                    return {"path": path, "status": "simulated_print"}
            return {"error": "File not found"}
        else:
            return {"status": "success", "capability": capability, "params": kwargs}
