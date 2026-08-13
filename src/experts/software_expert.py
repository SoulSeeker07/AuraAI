"""
Software Engineering Expert System
Location: src/experts/software_expert.py

Provides repository discovery, AST source code analysis, dependency inspection,
git health auditing, and refactoring proposals.

INVARIANT: Proposes actions to ExecutionCoordinator — NEVER executes code edits or shell mutations directly.
"""

from __future__ import annotations

import ast
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .base_expert import BaseExpertSystem
from .models import (
    DomainActionProposal,
    DomainFinding,
    DomainType,
    ExpertAnalysisResult,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class SoftwareEngineeringExpert(BaseExpertSystem):
    """
    Expert System for Software Engineering, AST Inspection, Code Health, and Git Auditing.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.SOFTWARE_ENGINEERING

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        # 1. Repository Discovery (G1)
        target_path_str = context.get("target_path") or context.get("file_path") or "."
        target_path = Path(target_path_str).resolve()
        workspace_root = Path(context.get("workspace_root") or target_path).resolve()

        py_files: list[Path] = []
        test_files: list[Path] = []
        config_files: list[str] = []

        if target_path.is_file():
            if target_path.suffix == ".py":
                py_files.append(target_path)
                if "test_" in target_path.name or "_test" in target_path.name:
                    test_files.append(target_path)
        elif target_path.is_dir():
            for root, dirs, files in os.walk(target_path):
                # Ignore hidden directories & virtual environments
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", ".venv", "__pycache__", "build", "dist")]
                for f in files:
                    fp = Path(root) / f
                    if f.endswith(".py"):
                        py_files.append(fp)
                        if "test_" in f or "_test" in f:
                            test_files.append(fp)
                    elif f in ("pyproject.toml", "requirements.txt", "setup.py", "tox.ini"):
                        config_files.append(f)

        findings.append(
            DomainFinding(
                category="repository_discovery",
                title="Workspace Codebase Discovery",
                description=f"Discovered {len(py_files)} Python source files and {len(test_files)} test files in '{target_path.name}'.",
                severity=SeverityLevel.INFO,
                evidence=[
                    f"Target Path: {target_path}",
                    f"Python Files Count: {len(py_files)}",
                    f"Test Files Count: {len(test_files)}",
                    f"Config Files Found: {', '.join(config_files) if config_files else 'None'}",
                ],
                location=str(target_path),
                confidence=0.98,
            )
        )

        # 2. AST Analysis (G2)
        ast_errors = 0
        missing_docstrings = 0
        complex_functions = 0

        for pf in py_files[:25]:  # Limit scan scope for performance
            try:
                code_text = pf.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(code_text, filename=str(pf))

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if not ast.get_docstring(node):
                            missing_docstrings += 1

                        # Complexity heuristic: line span > 30 lines
                        if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
                            if (node.end_lineno - node.lineno) > 30:
                                complex_functions += 1
                                findings.append(
                                    DomainFinding(
                                        category="ast_complexity",
                                        title=f"High Function Length: {node.name}()",
                                        description=f"Function '{node.name}' spans {node.end_lineno - node.lineno} lines, exceeding 30 lines.",
                                        severity=SeverityLevel.LOW,
                                        evidence=[f"Function: {node.name}", f"Span: {node.lineno}-{node.end_lineno} lines"],
                                        location=f"{pf}:{node.lineno}",
                                        confidence=0.90,
                                    )
                                )

            except SyntaxError as syn_err:
                ast_errors += 1
                findings.append(
                    DomainFinding(
                        category="ast_syntax_error",
                        title=f"Syntax Error in {pf.name}",
                        description=f"AST parsing failed: {syn_err.msg} at line {syn_err.lineno}.",
                        severity=SeverityLevel.HIGH,
                        evidence=[f"Error: {syn_err.msg}", f"Line: {syn_err.lineno}"],
                        location=f"{pf}:{syn_err.lineno}",
                        confidence=0.99,
                    )
                )

        if missing_docstrings > 0:
            findings.append(
                DomainFinding(
                    category="documentation_coverage",
                    title="Missing Class/Function Docstrings",
                    description=f"Identified {missing_docstrings} top-level functions/classes lacking docstrings.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Un-documented symbols count: {missing_docstrings}"],
                    location=str(target_path),
                    confidence=0.85,
                )
            )

        # 3. Dependency Inspection (G3)
        declared_deps: list[str] = []
        pyproject_file = workspace_root / "pyproject.toml"
        req_file = workspace_root / "requirements.txt"

        if pyproject_file.is_file():
            try:
                content = pyproject_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    if "=" in line or ">=" in line or "==" in line:
                        declared_deps.append(line.strip())
            except Exception:
                pass
        elif req_file.is_file():
            try:
                declared_deps = [l.strip() for l in req_file.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
            except Exception:
                pass

        findings.append(
            DomainFinding(
                category="dependency_audit",
                title="Dependency Configuration & Vulnerability Status",
                description=f"Inspected project dependencies ({len(declared_deps)} declared). Vulnerability status: UNKNOWN (reason: local vulnerability database unavailable).",
                severity=SeverityLevel.INFO,
                evidence=[
                    f"Declared Dependencies Count: {len(declared_deps)}",
                    "Vulnerability Database Status: UNAVAILABLE (Honest Unknown)",
                ],
                location=str(pyproject_file if pyproject_file.is_file() else (req_file if req_file.is_file() else target_path)),
                confidence=0.95,
            )
        )

        # 4. Git Health Inspection (G4)
        git_dir = workspace_root / ".git"
        if git_dir.exists():
            branch_name = "unknown"
            modified_files: list[str] = []
            try:
                res_b = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(workspace_root), capture_output=True, text=True, timeout=2)
                if res_b.returncode == 0:
                    branch_name = res_b.stdout.strip()
                res_s = subprocess.run(["git", "status", "--porcelain"], cwd=str(workspace_root), capture_output=True, text=True, timeout=2)
                if res_s.returncode == 0:
                    modified_files = [line.strip() for line in res_s.stdout.splitlines() if line.strip()]
            except Exception:
                pass

            findings.append(
                DomainFinding(
                    category="git_health",
                    title="Git Repository Health & Working Tree Status",
                    description=f"Git repository detected on branch '{branch_name}'. Working tree has {len(modified_files)} uncommitted/modified entries.",
                    severity=SeverityLevel.INFO if len(modified_files) == 0 else SeverityLevel.LOW,
                    evidence=[
                        f"Active Branch: {branch_name}",
                        f"Modified/Untracked Entries Count: {len(modified_files)}",
                    ],
                    location=str(git_dir),
                    confidence=0.96,
                )
            )

        # 5. Quality & Remediation Proposals (G5, G6, G7)
        if "refactor" in query_lower or "edit" in query_lower or "fix" in query_lower or ast_errors > 0:
            proposals.append(
                DomainActionProposal(
                    engine="engineering",
                    action="code.edit",
                    parameters={
                        "target_file": str(target_path),
                        "instruction": query,
                        "user_authorized": context.get("user_authorized", False),
                    },
                    description=f"Execute refactoring / code edit on {target_path.name}",
                    risk_level="low",
                )
            )

        # Always offer code quality analysis proposal
        proposals.append(
            DomainActionProposal(
                engine="engineering",
                action="code.analyze",
                parameters={"target_path": str(target_path)},
                description=f"Run quality analysis scan on {target_path.name}",
                risk_level="low",
            )
        )

        summary_msg = (
            f"Software engineering analysis complete for '{target_path.name}'. "
            f"Observed {len(py_files)} Python files, {ast_errors} syntax errors, "
            f"{complex_functions} complex functions, {len(findings)} findings."
        )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=summary_msg,
            findings=findings,
            proposals=proposals,
            data={
                "target_path": str(target_path),
                "py_files_count": len(py_files),
                "test_files_count": len(test_files),
                "ast_errors_count": ast_errors,
            },
        )
