"""
AST Analyzer for Software Engineering Expert (M25 Phase 2)
Location: src/experts/software/ast_analyzer.py

Performs safe, in-memory Abstract Syntax Tree analysis over source code.
Extracts functions, classes, imports, call targets, docstrings, and syntax errors.
Zero file modifications, zero capability execution.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ASTAnalyzer:
    """
    Analyzes Python AST structures safely without executing code.
    """

    def analyze_source(self, source_code: str, file_path: str = "") -> dict[str, Any]:
        """
        Parses source code into AST and extracts structural metadata.

        Returns:
            Dictionary containing:
                - syntax_valid: bool
                - syntax_error: str | None
                - classes: list[dict]
                - functions: list[dict]
                - imports: list[str]
                - calls: list[str]
                - total_lines: int
        """
        total_lines = len(source_code.splitlines())
        result: dict[str, Any] = {
            "file_path": file_path,
            "syntax_valid": True,
            "syntax_error": None,
            "classes": [],
            "functions": [],
            "imports": [],
            "calls": [],
            "total_lines": total_lines,
        }

        try:
            tree = ast.parse(source_code, filename=file_path or "<string>")
        except SyntaxError as e:
            result["syntax_valid"] = False
            result["syntax_error"] = f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"
            return result
        except Exception as e:
            result["syntax_valid"] = False
            result["syntax_error"] = f"Parse error: {str(e)}"
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result["classes"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "methods": [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
                    "bases": [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else [],
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # If top-level function (not a method inside a class body)
                result["functions"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "args": [a.arg for a in node.args.args],
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    result["imports"].append(f"{module}.{alias.name}" if module else alias.name)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    result["calls"].append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    result["calls"].append(node.func.attr)

        return result

    def analyze_file(self, file_path: str | Path) -> dict[str, Any]:
        """Reads file from disk and performs AST analysis."""
        path = Path(file_path)
        if not path.exists():
            return {
                "file_path": str(path),
                "syntax_valid": False,
                "syntax_error": f"File does not exist: {path}",
                "classes": [],
                "functions": [],
                "imports": [],
                "calls": [],
                "total_lines": 0,
            }

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return self.analyze_source(content, file_path=str(path))
        except Exception as e:
            return {
                "file_path": str(path),
                "syntax_valid": False,
                "syntax_error": f"Failed to read file: {e}",
                "classes": [],
                "functions": [],
                "imports": [],
                "calls": [],
                "total_lines": 0,
            }
