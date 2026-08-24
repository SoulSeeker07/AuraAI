"""
CodeAct Backend Adapter
Location: src/core/backends/adapters/codeact_backend.py

Connects MasterOrchestrator to DynamicCodeActExecutor for sandboxed artifact
synthesis (presentations, documents, spreadsheets, charts, conversions).
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from src.codeact.drafters import GroqDrafter
from src.codeact.executor import DynamicCodeActExecutor
from src.codeact.models import CodeActRequest
from src.core.backends.base_backend import BaseBackendAdapter
from src.core.planning.execution_result import ExecutionResult

logger = logging.getLogger(__name__)


class CodeActBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter executing general-purpose artifact generation via sandboxed CodeAct.
    """

    def __init__(self, executor: DynamicCodeActExecutor | None = None):
        self._executor = executor or DynamicCodeActExecutor(drafter=GroqDrafter())

    @property
    def name(self) -> str:
        return "CodeAct Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "codeact",
            "codeact.synthesize",
            "codeact.execute",
            "office.create_presentation",
            "office.create_document",
            "office.create_spreadsheet",
            "office.edit_document",
            "office.convert",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 5000.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        args = arguments or {}

        output_filename = (
            args.get("output_filename")
            or args.get("filename")
            or args.get("target_file")
            or args.get("file_path")
            or args.get("path")
            or "artifact.bin"
        )
        output_filename = Path(output_filename).name

        allowed_libraries = args.get("allowed_libraries") or []
        input_files = [Path(f) for f in args.get("input_files", []) if Path(f).exists()]
        destination_dir = args.get("destination_dir") or args.get("target_dir")

        if not destination_dir:
            goal_lower = goal.lower()
            if "desktop" in goal_lower:
                destination_dir = "$known_folder:desktop"
            elif "documents" in goal_lower or "document folder" in goal_lower:
                destination_dir = "$known_folder:documents"
            elif "downloads" in goal_lower:
                destination_dir = "$known_folder:downloads"
            else:
                destination_dir = os.getcwd()

        if str(destination_dir).startswith("$known_folder:"):
            try:
                import re
                from src.desktop.native.known_folders import resolve_known_folder
                raw_kf = str(destination_dir).split(":", 1)[1]
                parts = re.split(r"[\\/]", raw_kf, maxsplit=1)
                folder_key = parts[0].lower()
                destination_dir = str(resolve_known_folder(folder_key))
            except Exception as kf_err:
                logger.warning(f"Could not resolve known folder '{destination_dir}': {kf_err}")
                destination_dir = os.getcwd()

        # Build request
        req = CodeActRequest(
            goal=goal,
            output_filename=output_filename,
            allowed_libraries=allowed_libraries,
            input_files=input_files,
            max_repair_attempts=int(args.get("max_repair_attempts", 3)),
            timeout_seconds=int(args.get("timeout_seconds", 30)),
        )

        res = self._executor.run(req)

        if res.status == "success" and res.output_path:
            # Move to destination directory
            dest_dir_path = Path(destination_dir).resolve()
            dest_dir_path.mkdir(parents=True, exist_ok=True)
            final_file_path = dest_dir_path / output_filename
            try:
                shutil.copy2(res.output_path, final_file_path)
            except Exception as copy_exc:
                logger.warning(f"Error copying artifact to '{final_file_path}': {copy_exc}")
                final_file_path = res.output_path

            file_size = final_file_path.stat().st_size if final_file_path.exists() else 0
            return ExecutionResult(
                success=True,
                planner="codeact",
                goal=goal,
                observations=[
                    f"Synthesized artifact '{output_filename}' ({file_size} bytes) via CodeAct in {len(res.attempts)} attempt(s)"
                ],
                data={
                    "path": str(final_file_path),
                    "filename": output_filename,
                    "size": file_size,
                    "attempts_used": len(res.attempts),
                    "status": "created",
                },
            )
        else:
            return ExecutionResult(
                success=False,
                planner="codeact",
                goal=goal,
                observations=[
                    f"CodeAct artifact synthesis failed for '{output_filename}': {res.final_error}"
                ],
                data={
                    "error": res.final_error,
                    "attempts_used": len(res.attempts),
                    "status": "failed",
                },
            )
