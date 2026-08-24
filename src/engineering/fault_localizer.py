"""
Fault Localization & AST Slicing Engine
Location: src/engineering/fault_localizer.py

Analyzes structured test failures, filters out test files, and resolves stack trace
coordinates to concrete source AST symbols (functions, methods, classes) for targeted repair.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .safety_ceiling import is_test_file, normalize_relative_path
from .test_runner import StackFrame, TestFailureFrame


@dataclass
class FaultCandidate:
    """Target source coordinate identified for code repair."""
    file_path: str
    line_number: int
    symbol_name: str
    symbol_type: str  # "function", "class", "method", "module"
    line_content: str = ""
    start_line: int = 1
    end_line: int = 1


class FaultLocalizer:
    """
    Resolves test failure frames to candidate source code AST symbols.
    """

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or os.getcwd()).resolve()

    def localize_fault(
        self,
        failure: TestFailureFrame,
        repo_root: str | Path | None = None,
    ) -> list[FaultCandidate]:
        """
        Extract source fault candidates from a test failure frame.
        Guarantees that test files are filtered out, preserving test immunity.
        """
        root = Path(repo_root or self.repo_root).resolve()
        candidates: list[FaultCandidate] = []
        
        # Iterate stack frames in reverse (deepest execution frame first)
        frames_to_check = list(reversed(failure.stack_frames))

        for frame in frames_to_check:
            raw_path = Path(frame.file_path)
            # 1. Containment check: Frame path MUST resolve inside repo_root
            if raw_path.is_absolute():
                resolved_frame = raw_path.resolve()
            else:
                resolved_frame = (root / raw_path).resolve()

            try:
                rel = resolved_frame.relative_to(root)
            except ValueError:
                # Frame is outside repo_root (e.g. stdlib or external site-packages) -> strictly skip
                continue

            rel_path = str(rel).replace("\\", "/")

            # 2. Strictly filter out test files and dependencies from fault localization candidates
            if is_test_file(rel_path, root):
                continue
            if any(part in (".venv", "venv", "site-packages", "node_modules") for part in resolved_frame.parts):
                continue

            if not resolved_frame.exists() or not resolved_frame.is_file():
                continue

            symbol_info = self._resolve_ast_symbol(resolved_frame, frame.line_number)
            candidates.append(
                FaultCandidate(
                    file_path=rel_path,
                    line_number=frame.line_number,
                    symbol_name=symbol_info["symbol_name"],
                    symbol_type=symbol_info["symbol_type"],
                    line_content=symbol_info["line_content"],
                    start_line=symbol_info["start_line"],
                    end_line=symbol_info["end_line"],
                )
            )

        return candidates

    def _resolve_ast_symbol(self, file_path: Path, line_number: int) -> dict[str, Any]:
        """Parse source file with AST to find enclosing symbol at line_number."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return {
                "symbol_name": "<unknown>",
                "symbol_type": "module",
                "line_content": "",
                "start_line": line_number,
                "end_line": line_number,
            }

        lines = content.splitlines()
        line_content = lines[line_number - 1] if 0 < line_number <= len(lines) else ""

        candidates: list[tuple[int, Any]] = []
        symbol_type = "module"
        symbol_name = file_path.stem

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                if start <= line_number <= end:
                    candidates.append((end - start, node))

        target_node = None
        if candidates:
            # Sort by span ascending to select the innermost / most specific enclosing symbol
            candidates.sort(key=lambda x: x[0])
            target_node = candidates[0][1]
            symbol_name = target_node.name
            symbol_type = "class" if isinstance(target_node, ast.ClassDef) else "function"

        start_l = getattr(target_node, "lineno", line_number) if target_node else line_number
        end_l = getattr(target_node, "end_lineno", line_number) if target_node else line_number

        return {
            "symbol_name": symbol_name,
            "symbol_type": symbol_type,
            "line_content": line_content.strip(),
            "start_line": start_l,
            "end_line": end_l,
        }


__all__ = [
    "FaultCandidate",
    "FaultLocalizer",
]
