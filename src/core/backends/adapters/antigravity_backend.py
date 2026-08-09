"""
Coding Backend Adapter
Location: src/core/backends/adapters/antigravity_backend.py

Routes coding requests through the EngineeringManager (src/engineering/).
Provides honest success/failure based on real operations — never returns a
hardcoded success.

Capability contract:
    - code.analyze   → analyze repository or target files via AST
    - code.edit      → apply file edits via CodeEditor (requires edit_operations)
    - code.report    → quality + dependency report
    - code.modify    → alias for code.edit
    - code.refactor  → alias for code.edit
    - code.test      → alias for code.analyze (test coverage scan)
    - coding         → routes by sub-operation in arguments

LLM-guided code generation is NOT available here.
That is scheduled for M20 (Coding Intelligence 2.0).

Foundation Truth Pass — Phase 0 repair.
"""

import logging
from pathlib import Path
from typing import Any

try:
    from ...planning.execution_result import ExecutionResult
    from ..base_backend import BaseBackendAdapter
except (ImportError, ValueError):
    from core.planning.execution_result import ExecutionResult
    from core.backends.base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)

# Capabilities this backend genuinely handles
_SUPPORTED_CAPABILITIES = frozenset(
    [
        "coding",
        "code.analyze",
        "code.edit",
        "code.modify",
        "code.refactor",
        "code.report",
        "code.test",
    ]
)

# Capabilities that require LLM-guided generation (not yet implemented)
_DEFERRED_TO_M20 = frozenset(
    [
        "code.generate",
        "code.create",
        "code.implement",
    ]
)


class CodingBackendAdapter(BaseBackendAdapter):
    """
    Coding backend adapter backed by EngineeringManager.

    Routes to the real src/engineering/ subsystem for:
        - Repository and file analysis (AST-based)
        - Quality and dependency reports
        - File editing with validation and rollback

    Returns honest failure for:
        - LLM-guided code generation (deferred to M20)
        - Missing target files or edit operations
        - Any operation where no real work can be performed
    """

    @property
    def name(self) -> str:
        return "Coding Backend (EngineeringManager)"

    @property
    def capabilities(self) -> list[str]:
        return list(_SUPPORTED_CAPABILITIES)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 800.0,
            "cost": 0.0,
            "is_local": True,
            "version": "2.0.0",
            "backed_by": "src/engineering/EngineeringManager",
            "note": (
                "LLM-guided code generation deferred to M20 (Coding Intelligence 2.0). "
                "This backend performs real analysis and file editing only."
            ),
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        """
        Execute a coding capability using EngineeringManager.

        Never returns success=True unless real work was performed and verified.
        """
        args = arguments or {}
        logger.info(
            f"CodingBackendAdapter: capability='{capability}' goal='{goal[:80]}'"
        )

        # ── Deferred capabilities (M20) ────────────────────────────────────
        if capability in _DEFERRED_TO_M20 or self._is_generation_request(goal, args):
            return self._not_implemented_result(goal, capability)

        # ── Resolve repository path ────────────────────────────────────────
        repo_path = self._resolve_repo_path(args)

        # ── Route by capability ────────────────────────────────────────────
        if capability in ("code.edit", "code.modify", "code.refactor"):
            return self._execute_edit(goal, args, repo_path)

        if capability in ("code.analyze", "code.test", "coding"):
            # If edit_operations provided, run edit; otherwise analyze
            if args.get("edit_operations") or args.get("new_content"):
                return self._execute_edit(goal, args, repo_path)
            return self._execute_analyze(goal, args, repo_path)

        if capability == "code.report":
            return self._execute_report(goal, args, repo_path)

        # Unknown capability — honest failure
        return ExecutionResult(
            success=False,
            planner="coding",
            goal=goal,
            confidence=0.0,
            observations=[
                f"Coding backend does not handle capability '{capability}'.",
                f"Supported: {sorted(_SUPPORTED_CAPABILITIES)}",
            ],
            data={"backend": self.name, "capability": capability},
        )

    # ── Private: route handlers ────────────────────────────────────────────

    def _execute_analyze(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        """
        Analyze repository or target files using EngineeringManager.
        Returns real analysis data — never a hardcoded result.
        """
        import re

        target_files: list[str] = args.get("target_files", [])
        if not target_files:
            # Check alternative argument keys
            for k in ["target", "file_path", "path", "file"]:
                val = args.get(k)
                if val and isinstance(val, str) and val.endswith(".py"):
                    target_files.append(val)

        if not target_files:
            # Auto-extract .py paths from goal string
            found_py = re.findall(r"[a-zA-Z0-9_\-\./\\]+\.py", goal)
            if found_py:
                target_files.extend(found_py)

        try:
            from ....engineering.engineering_manager import EngineeringManager

            mgr = EngineeringManager(
                repository_path=repo_path,
                enable_lsp=False,       # LSP disabled for speed in Foundation pass
                enable_auto_sync=False,
            )

            if target_files:
                # Per-file AST analysis
                file_results = []
                analyzed = []
                for file_str in target_files:
                    file_path = Path(file_str)
                    if not file_path.is_absolute():
                        file_path = repo_path / file_str
                    if not file_path.exists():
                        file_results.append(
                            {"file": file_str, "error": "File not found"}
                        )
                        continue
                    try:
                        ast_node = mgr.understand_code(file_path)
                        file_results.append(
                            {
                                "file": file_str,
                                "analyzed": True,
                                "node_type": getattr(ast_node, "type", "unknown"),
                            }
                        )
                        analyzed.append(file_str)
                    except Exception as e:
                        file_results.append({"file": file_str, "error": str(e)})

                mgr.close()
                success = len(analyzed) > 0
                return ExecutionResult(
                    success=success,
                    planner="coding",
                    goal=goal,
                    confidence=1.0 if success else 0.0,
                    observations=[
                        f"Analyzed {len(analyzed)}/{len(target_files)} file(s).",
                    ]
                    + [
                        f"✓ {r['file']}"
                        if r.get("analyzed")
                        else f"✗ {r['file']}: {r.get('error')}"
                        for r in file_results
                    ],
                    data={
                        "backend": self.name,
                        "capability": "code.analyze",
                        "analyzed_files": analyzed,
                        "file_results": file_results,
                        "repository_path": str(repo_path),
                    },
                )

            # Repository-level analysis
            try:
                analysis = mgr.analyze_repository()
                mgr.close()
                return ExecutionResult(
                    success=True,
                    planner="coding",
                    goal=goal,
                    confidence=1.0,
                    observations=[
                        f"Repository analysis complete: {repo_path.name}",
                        f"Files: {analysis.get('total_files', 'unknown')}",
                        f"Issues: {analysis.get('total_issues', 'unknown')}",
                    ],
                    data={
                        "backend": self.name,
                        "capability": "code.analyze",
                        "analysis": analysis,
                        "repository_path": str(repo_path),
                    },
                )
            except Exception as e:
                mgr.close()
                return self._error_result(goal, "code.analyze", str(e))

        except ImportError as e:
            return self._error_result(
                goal, "code.analyze", f"EngineeringManager import failed: {e}"
            )
        except Exception as e:
            return self._error_result(goal, "code.analyze", str(e))

    def _execute_edit(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        """
        Apply file edits using CodeEditor with validation and rollback.
        Requires edit_operations or (target_files + new_content) in arguments.
        Returns real success/failure based on actual file write outcomes.
        """
        edit_operations: list[dict] = args.get("edit_operations", [])
        target_files: list[str] = args.get("target_files", [])
        new_content: str = args.get("new_content", "")

        # Build edit_operations from flat args if not provided as structured list
        if not edit_operations and target_files and new_content:
            edit_operations = [
                {"file_path": f, "new_content": new_content}
                for f in target_files
            ]

        if not edit_operations:
            return ExecutionResult(
                success=False,
                planner="coding",
                goal=goal,
                confidence=0.0,
                observations=[
                    "File edit requires 'edit_operations' (list of {file_path, new_content}) "
                    "or 'target_files' + 'new_content' in arguments.",
                    "LLM-guided code generation is scheduled for M20 (Coding Intelligence 2.0). "
                    "The coding backend cannot generate content from a goal description alone yet.",
                ],
                data={"backend": self.name, "capability": "code.edit"},
            )

        try:
            from ....engineering.engineering_manager import EngineeringManager

            mgr = EngineeringManager(
                repository_path=repo_path,
                enable_lsp=False,
                enable_auto_sync=False,
            )

            succeeded = []
            failed = []
            observations = []

            for op in edit_operations:
                file_path_str: str = op.get("file_path", "")
                content: str = op.get("new_content", "")

                if not file_path_str or not content:
                    failed.append(
                        {"file": file_path_str, "error": "Missing file_path or new_content"}
                    )
                    continue

                result = mgr.code_editor.edit_file(
                    file_path=file_path_str,
                    new_content=content,
                    backup=True,
                    validate=True,
                )

                if result.success:
                    succeeded.append(file_path_str)
                    observations.append(f"✓ Edited: {file_path_str}")
                else:
                    failed.append({"file": file_path_str, "errors": result.errors})
                    observations.append(
                        f"✗ Failed: {file_path_str} — {'; '.join(result.errors)}"
                    )

            mgr.close()
            overall_success = len(succeeded) > 0 and len(failed) == 0

            return ExecutionResult(
                success=overall_success,
                planner="coding",
                goal=goal,
                confidence=1.0 if overall_success else 0.5 if succeeded else 0.0,
                observations=[
                    f"Edit complete: {len(succeeded)} succeeded, {len(failed)} failed."
                ]
                + observations,
                data={
                    "backend": self.name,
                    "capability": "code.edit",
                    "modified_files": succeeded,
                    "failed_files": [f["file"] for f in failed],
                    "repository_path": str(repo_path),
                },
            )

        except ImportError as e:
            return self._error_result(
                goal, "code.edit", f"EngineeringManager import failed: {e}"
            )
        except Exception as e:
            return self._error_result(goal, "code.edit", str(e))

    def _execute_report(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        """
        Generate a quality and dependency report for the repository.
        """
        try:
            from ....engineering.engineering_manager import EngineeringManager

            mgr = EngineeringManager(
                repository_path=repo_path,
                enable_lsp=False,
                enable_auto_sync=False,
            )
            report = mgr.get_quality_report()
            mgr.close()

            return ExecutionResult(
                success=True,
                planner="coding",
                goal=goal,
                confidence=1.0,
                observations=[
                    f"Quality report generated for: {repo_path.name}",
                    f"Issues found: {report.get('total_issues', 'unknown')}",
                    f"Quality score: {report.get('quality_score', 'unknown')}",
                ],
                data={
                    "backend": self.name,
                    "capability": "code.report",
                    "report": report,
                    "repository_path": str(repo_path),
                },
            )

        except ImportError as e:
            return self._error_result(
                goal, "code.report", f"EngineeringManager import failed: {e}"
            )
        except Exception as e:
            return self._error_result(goal, "code.report", str(e))

    # ── Private: helpers ───────────────────────────────────────────────────

    def _resolve_repo_path(self, args: dict[str, Any]) -> Path:
        """Resolve repository path from arguments or fall back to cwd."""
        repo_path_str = args.get("repository_path") or args.get("project_path")
        if repo_path_str:
            p = Path(repo_path_str)
            if p.exists():
                return p.resolve()
        return Path.cwd().resolve()

    def _is_generation_request(self, goal: str, args: dict[str, Any]) -> bool:
        """
        Detect if the request is asking for LLM-guided code generation.
        These are deferred to M20 (Coding Intelligence 2.0).
        """
        generation_signals = [
            "write a function",
            "implement",
            "create a class",
            "generate code",
            "write code for",
            "build a module",
            "write me",
            "write a script",
            "write a python script",
            "write script",
            "script to",
            "write python",
            "create script",
            "generate script",
            "generate python script",
            "generate a python script",
            "generate a script",
        ]
        goal_lower = goal.lower()
        has_signal = any(s in goal_lower for s in generation_signals)
        has_no_files = not args.get("target_files") and not args.get("edit_operations")
        return has_signal and has_no_files

    def _not_implemented_result(self, goal: str, capability: str) -> ExecutionResult:
        """
        Return an honest not-implemented result for M20-deferred capabilities.
        Never returns success=True.
        """
        return ExecutionResult(
            success=False,
            planner="coding",
            goal=goal,
            confidence=0.0,
            observations=[
                "LLM-guided code generation is not yet implemented in the coding backend.",
                "This capability is scheduled for M20 (Coding Intelligence 2.0).",
                "Current coding capabilities: code.analyze (AST analysis), "
                "code.edit (file editing with validation), code.report (quality report).",
                "To use code editing, provide 'target_files' and 'edit_operations' in arguments.",
            ],
            data={
                "backend": self.name,
                "capability": capability,
                "deferred_to": "M20 — Coding Intelligence 2.0",
            },
        )

    def _error_result(
        self, goal: str, capability: str, error: str
    ) -> ExecutionResult:
        """Return a structured error result — never a fake success."""
        logger.error(f"CodingBackendAdapter error [{capability}]: {error}")
        return ExecutionResult(
            success=False,
            planner="coding",
            goal=goal,
            confidence=0.0,
            observations=[
                f"Coding backend encountered an error during '{capability}'.",
                f"Error: {error}",
            ],
            data={"backend": self.name, "capability": capability, "error": error},
        )


# Backward-compatible alias — old name kept so nothing breaks at import time
AntigravityBackendAdapter = CodingBackendAdapter
