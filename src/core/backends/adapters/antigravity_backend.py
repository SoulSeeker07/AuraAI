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
    from .agy_subprocess_client import AgyConfig, AgyError, AgySubprocessClient
except (ImportError, ValueError):
    from core.planning.execution_result import ExecutionResult
    from core.backends.base_backend import BaseBackendAdapter
    from core.backends.adapters.agy_subprocess_client import (
        AgyConfig,
        AgyError,
        AgySubprocessClient,
    )

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
        "code.generate",
        "code.create",
        "code.implement",
        "code.debug",
        "code.execute",
    ]
)

# No capabilities are deferred to M20 anymore
_DEFERRED_TO_M20 = frozenset([])

# M20.4a: hard cap for unscoped (no target_files) repo-level analyze/report
# calls. This is a stopgap — the real fix (M20.4b) is .gitignore-aware
# walking inside EngineeringManager itself, which this constant does not
# touch. Tune this number based on real repo sizes; it exists to turn a
# multi-minute hang on an 80K+-file repo into an immediate, honest
# "scope this" response instead.
_MAX_UNSCOPED_ANALYZE_FILES = 2000
_ANALYZE_SKIP_DIRS = frozenset(
    {".venv", "venv", "env", "node_modules", ".git", "__pycache__",
     ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".tox"}
)

# M20.4a — hard cap on repo-level analyze/report scans. This is a stopgap:
# it stops the adapter from walking huge trees (e.g. an accidentally-included
# .venv/node_modules) before handing off to EngineeringManager. The correct
# fix (M20.4b) is .gitignore-aware walking inside EngineeringManager itself —
# this cap doesn't replace that, it just bounds the damage until it lands.
_ANALYZE_FILE_CAP = 2000
_ANALYZE_SCAN_SKIP_DIRS = frozenset(
    [".git", ".venv", "venv", "env", "node_modules", "__pycache__",
     ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".tox"]
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

    def __init__(
        self,
        *args: Any,
        agy_client: "AgySubprocessClient | None" = None,
        world_model: Any | None = None,
        **kwargs: Any,
    ):
        # *args/**kwargs pass through untouched to BaseBackendAdapter in case
        # it takes its own init args — this adapter adds agy_client and world_model.
        super().__init__(*args, **kwargs)
        # Injectable so tests can pass a mock instead of shelling out to the
        # real `agy` binary (see test_coding_backend_wiring_m20.py).
        self.agy_client = agy_client or AgySubprocessClient(AgyConfig())
        self.world_model = world_model

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

        operation = "unknown"
        language = "unknown"
        clean_goal = goal

        goal_lower = goal.lower()
        edit_verbs = ["add", "modify", "update", "edit", "change", "refactor"]

        if capability in ("code.analyze", "workspace.walk", "code.inspect"):
            operation = "analyze"
        elif capability in ("code.edit", "code.modify", "code.refactor"):
            operation = "edit"
        elif capability in ("code.generate", "code.create", "code.implement"):
            operation = "generate"
        elif capability in ("code.debug", "code.fix"):
            operation = "debug"
        elif capability == "code.test":
            operation = "test"
        elif capability == "code.report":
            operation = "report"
        elif capability == "code.execute":
            operation = "execute"
        elif any(v in goal_lower for v in edit_verbs):
            operation = "edit"
        elif "analyze" in goal_lower or "inspect" in goal_lower or "explain" in goal_lower:
            operation = "analyze"
        elif "test" in goal_lower:
            operation = "test"
        elif "debug" in goal_lower or "fix" in goal_lower:
            operation = "debug"
        elif self._is_generation_request(goal, args):
            operation = "generate"
        elif "execute " in goal_lower or "run " in goal_lower:
            operation = "execute"
        else:
            if args.get("edit_operations") or args.get("new_content"):
                operation = "edit"
            else:
                operation = "analyze"

        if "python" in goal_lower:
            language = "python"
            clean_goal = clean_goal.lower().replace("python", "").replace("code", "").strip()
        elif "javascript" in goal_lower or "js" in goal_lower:
            language = "javascript"
        elif "typescript" in goal_lower or "ts" in goal_lower:
            language = "typescript"

        import os
        verbosity = os.environ.get("AURA_VERBOSITY", "normal")
        if verbosity in ("developer", "debug", "trace"):
            print("\n" + "=" * 60)
            print("CODING BACKEND TRACE")
            print("=" * 60)
            print(f"Operation   : {operation}")
            if operation == "generate":
                print(f"Language    : {language}")
                print(f"Goal        : {clean_goal}")
            else:
                print(f"Capability  : {capability}")
                print(f"Goal        : {goal}")
            print("=" * 60 + "\n")

        # ── Route by capability ────────────────────────────────────────────
        repo_path = self._resolve_repo_path(args)

        # ── Route by capability ────────────────────────────────────────────
        if capability == "code.execute" or operation == "execute":
            return self._execute_run(goal, args, repo_path)

        if capability == "code.debug" or operation == "debug":
            return self._execute_debug(goal, args, repo_path)

        if capability in ("code.edit", "code.modify", "code.refactor") or operation == "edit":
            return self._execute_edit(goal, args, repo_path)

        if capability in ("code.generate", "code.create", "code.implement") or operation == "generate":
            return self._execute_generate(goal, args, repo_path)

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

    def _execute_run(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        import subprocess
        
        script_path = args.get("file_path") or args.get("script") or "app.py"
        abs_path = (repo_path / script_path).resolve()
        
        if not abs_path.exists():
            # If the LLM passed a generic command instead of a file
            command = args.get("command")
            if command:
                cmd = command.split()
            else:
                return self._error_result(
                    goal, "code.execute", f"Target file '{script_path}' not found at {abs_path}"
                )
        else:
            venv_python = repo_path / ".venv" / "Scripts" / "python.exe"
            if not venv_python.exists():
                venv_python = Path("python")
            cmd = [str(venv_python), str(abs_path)]
            
        logger.info(f"Executing: {' '.join(cmd)}")
        
        try:
            # M20.5 Execution Model (CLI Default)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(repo_path)
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            obs = ["Execution completed."]
            if stdout:
                obs.append(f"STDOUT:\n{stdout}")
            if stderr:
                obs.append(f"STDERR:\n{stderr}")
                
            return ExecutionResult(
                success=result.returncode == 0,
                planner="coding",
                goal=goal,
                confidence=1.0,
                observations=obs,
                data={
                    "returncode": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr
                }
            )
            
        except subprocess.TimeoutExpired as e:
            # M20.5: gracefully catch timeout for GUI apps or long-running servers
            partial_stdout = e.stdout.decode('utf-8', errors='replace').strip() if isinstance(e.stdout, bytes) else (e.stdout or "").strip()
            obs = ["Process timed out after 10 seconds (still running)."]
            if partial_stdout:
                obs.append(f"Partial STDOUT:\n{partial_stdout}")
            return ExecutionResult(
                success=True,
                planner="coding",
                goal=goal,
                confidence=0.8,
                observations=obs,
                data={"timeout": True}
            )
        except Exception as e:
            return self._error_result(goal, "code.execute", f"Failed to execute: {e}")

    def _execute_generate(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        import os
        import json
        from ai.registry import build_provider_manager
        from ai.models import ChatRequest, ChatMessage
        from .coding_models import RequirementModel, CodeGenerationPlan
        from .workspace_policy import WorkspacePolicy, WorkspacePolicyError
        
        try:
            from ....engineering.engineering_manager import EngineeringManager
        except (ImportError, ValueError):
            from engineering.engineering_manager import EngineeringManager
            
        provider_mgr = build_provider_manager(os.environ)
        
        # 1. Requirement Extraction (still Groq — cheap, and req_model feeds
        #    both the agy prompt and the Groq fallback prompt below)
        req_sys = (
            "You are an expert technical product manager. Extract the requirements for the requested feature. "
            "Output exactly a JSON object matching this schema: "
            '{"project_name": "...", "language": "...", "explicit_requirements": ["..."], "inferred_requirements": ["..."]}. '
            "Do not output any markdown formatting."
        )
        req_msg = [
            ChatMessage(role="system", content=req_sys),
            ChatMessage(role="user", content=f"Goal: {goal}\nArguments: {json.dumps(args, default=str)}")
        ]
        
        req_resp = provider_mgr.chat(ChatRequest(messages=req_msg))
        try:
            req_data = json.loads(req_resp.text.strip())
            req_model = RequirementModel(**req_data)
        except Exception as e:
            return self._error_result(goal, "code.generate", f"Failed to extract RequirementModel: {e}\nResponse: {req_resp.text}")

        # 2. Structured Code Plan — try agy first (workspace-aware, sees the
        #    real repo via --add-dir), fall back to the direct Groq JSON
        #    generation this backend used before M20.3 if agy is unavailable
        #    or its output doesn't validate as a CodeGenerationPlan.
        plan, plan_source = self._get_code_generation_plan(
            goal, req_model, repo_path, provider_mgr, CodeGenerationPlan, ChatMessage, ChatRequest
        )
        if plan is None:
            return self._error_result(
                goal, "code.generate",
                "Both agy and the Groq fallback failed to produce a valid CodeGenerationPlan."
            )

        # 3. Workspace Policy & File Safety
        policy = WorkspacePolicy(repo_path)
        mgr = EngineeringManager(repository_path=repo_path, enable_lsp=False, enable_auto_sync=False)
        
        file_results = []
        syntax_passed = True
        imports_passed = True
        repairs = 0
        
        for file in plan.files:
            try:
                target_path = policy.authorize_write(file.path, allow_overwrite=args.get("allow_overwrite", False))
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(file.content, encoding="utf-8")
                
                # 4. Granular Validation & Targeted Repair
                max_retries = 3
                file_valid = False
                
                for attempt in range(max_retries):
                    try:
                        ast_node = mgr.understand_code(target_path)
                        # Syntax and AST passed
                        file_results.append(f"✓ {file.path}")
                        file_valid = True
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            file_results.append(f"✗ {file.path}: Validation failed after {max_retries} attempts ({e})")
                            break
                        else:
                            repairs += 1
                            # Repair always goes through Groq directly (fast,
                            # single-file, no workspace reasoning needed) —
                            # independent of whether the original plan came
                            # from agy or the Groq fallback above.
                            repair_prompt = (
                                f"The file {file.path} failed syntax validation with error: {e}. "
                                f"Current content:\n{target_path.read_text(encoding='utf-8')}\n\n"
                                "Provide a corrected JSON object matching this schema, no markdown: "
                                '{"files": [{"path": "relative/path.py", "content": "fixed source code"}]}'
                            )
                            repair_msg = [
                                ChatMessage(
                                    role="system",
                                    content="You are an expert software engineer fixing a syntax/validation error.",
                                ),
                                ChatMessage(role="user", content=repair_prompt),
                            ]
                            repair_resp = provider_mgr.chat(ChatRequest(messages=repair_msg, max_tokens=4096))
                            try:
                                fix_data = json.loads(repair_resp.text.strip())
                                fixed_plan = CodeGenerationPlan(**fix_data)
                                if fixed_plan.files:
                                    # Ensure policy still applies to the repaired file
                                    fixed_path = policy.authorize_write(fixed_plan.files[0].path, allow_overwrite=True)
                                    fixed_path.write_text(fixed_plan.files[0].content, encoding="utf-8")
                            except Exception:
                                pass # Let it fail next iteration
                                
                if not file_valid:
                    syntax_passed = False
                    
            except WorkspacePolicyError as e:
                file_results.append(f"✗ {file.path}: Policy violation ({e})")
                syntax_passed = False
            except Exception as e:
                file_results.append(f"✗ {file.path}: {e}")
                syntax_passed = False
                
        mgr.close()
        
        # 5. Final Truthful Result
        return ExecutionResult(
            success=syntax_passed,
            planner="coding",
            goal=goal,
            confidence=1.0 if syntax_passed else 0.5,
            observations=[
                f"Plan source     : {plan_source}",
                f"Generated files : {len(plan.files)}",
                f"Syntax          : {'PASS' if syntax_passed else 'FAIL'}",
                f"Imports         : {'PASS' if imports_passed else 'FAIL'}",
                "Tests           : NOT RUN",
                "Runtime         : NOT VERIFIED",
                f"Repairs         : {repairs}",
                ""
            ] + file_results,
            data={
                "backend": self.name,
                "capability": "code.generate",
                "plan_source": plan_source,
                "repairs": repairs,
                "requirements": req_model.model_dump(),
            }
        )

    def _extract_candidate_identifiers(self, text: str) -> list[str]:
        """Extract candidate PascalCase or snake_case identifiers from user goal."""
        import re
        # Match words with at least 3 chars starting with letter/underscore
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", text)
        stop_words = {
            "python", "code", "file", "make", "create", "write", "build", "app", "system",
            "database", "function", "class", "model", "test", "with", "that", "from",
            "import", "user", "using", "implement", "feature", "please", "into"
        }
        candidates: list[str] = []
        for t in tokens:
            if t.lower() not in stop_words and t not in candidates:
                candidates.append(t)
        return candidates

    def _get_world_context(self, goal: str, repo_path: Path) -> str:
        """
        Extract live workspace and targeted symbol context from WorldModel.
        Strictly best-effort: failures/timeouts return empty string and never block generation.
        """
        if not self.world_model:
            return ""

        parts: list[str] = []
        try:
            # 1. Fast workspace state (git branch, dirty status, project type, active editor file)
            ws_res = self.world_model.query_sync(entity="all", domain="workspace", timeout=0.5)
            if ws_res and ws_res.facts:
                active_doc = next((f.value for f in ws_res.facts if f.entity == "active_file" and f.value), None)
                ws_facts = [
                    f"• {f.entity}: {f.value}"
                    for f in ws_res.facts
                    if f.value and f.entity != "active_file"
                ]
                context_lines = []
                if active_doc:
                    context_lines.append(f"Active Editor File: `{active_doc}`")
                if ws_facts:
                    context_lines.append("Workspace State:\n" + "\n".join(ws_facts))
                if context_lines:
                    parts.append("\n\n".join(context_lines))

            # 2. Extract at most 3 potential symbols mentioned in goal
            identifiers = self._extract_candidate_identifiers(goal)[:3]
            if identifiers:
                sym_entities = [f"class:{ident}" for ident in identifiers] + [
                    f"function:{ident}" for ident in identifiers
                ]
                sym_res_list = self.world_model.query_multi_sync(
                    entities=sym_entities, domain="symbol", timeout=0.8
                )
                found_symbols = []
                for res in sym_res_list:
                    for f in res.facts:
                        if f.value and f.value != "not_found":
                            found_symbols.append(f"• {f.entity} located in `{f.value}`")

                if found_symbols:
                    parts.append("Referenced Symbols:\n" + "\n".join(found_symbols))

        except Exception as e:
            logger.debug("WorldModel context enrichment skipped: %s", e)

        return "\n\n".join(parts)

    def _get_code_generation_plan(
        self, goal, req_model, repo_path, provider_mgr, CodeGenerationPlan, ChatMessage, ChatRequest
    ):
        """
        Returns (plan, source) where source is "agy" or "groq", or
        (None, None) if both paths fail.

        Tries agy first — it can inspect the real repo via --add-dir
        instead of generating blind from a requirements JSON blob — and
        falls back to the direct Groq JSON generation this backend used
        before M20.3 if agy is unavailable or its output doesn't validate.
        """
        import json as _json

        world_context = self._get_world_context(goal, repo_path)
        context_block = f"\n\nLive System Context:\n{world_context}\n" if world_context else ""

        agy_goal = (
            f"Goal: {goal}\n"
            f"Requirements: {_json.dumps(req_model.model_dump())}"
            f"{context_block}\n\n"
            "Put new projects in their own subdirectory (e.g., `calculator_app/app.py`), never directly in the repository root. "
            "Return ONLY a JSON object matching this schema, no markdown, "
            "no preamble: "
            '{"files": [{"path": "relative/path.py", "content": "full source code"}]}'
        )
        try:
            result = self.agy_client.run_plan(goal=agy_goal, add_dir=str(repo_path))
            plan = CodeGenerationPlan(**result.raw)
            logger.info(
                "code.generate: using agy-sourced plan (%d files, %.1fs)",
                len(plan.files), result.elapsed_s,
            )
            return plan, "agy"
        except AgyError as e:
            logger.warning("agy unavailable for code.generate (%s); falling back to Groq", e)
        except Exception as e:
            logger.warning(
                "agy output failed CodeGenerationPlan validation (%s); falling back to Groq", e
            )

        # Groq fallback — identical to the pre-M20.3 flow.
        plan_sys = (
            "You are an expert software engineer. Implement the feature. "
            "Put new projects in their own subdirectory (e.g., `calculator_app/app.py`), never directly in the repository root. "
            "Output exactly a JSON object matching this schema: "
            '{"files": [{"path": "relative/path.py", "content": "full source code"}]}. '
            "Do not output any markdown formatting."
        )
        plan_msg = [
            ChatMessage(role="system", content=plan_sys),
            ChatMessage(role="user", content=f"Requirements:\n{_json.dumps(req_model.model_dump())}"),
        ]
        plan_resp = provider_mgr.chat(ChatRequest(messages=plan_msg, max_tokens=4096))
        try:
            plan_data = _json.loads(plan_resp.text.strip())
            plan = CodeGenerationPlan(**plan_data)
            return plan, "groq"
        except Exception as e:
            logger.error(
                "Groq fallback also failed to produce CodeGenerationPlan: %s. Response: %s",
                e, plan_resp.text,
            )
            return None, None

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
        except (ImportError, ValueError):
            try:
                from engineering.engineering_manager import EngineeringManager
            except ImportError as e:
                import traceback
                tb = traceback.format_exc()
                return self._error_result(
                    goal, "code.analyze", f"EngineeringManager import failed: {e}\nTraceback:\n{tb}"
                )
            except Exception as e:
                return self._error_result(goal, "code.analyze", str(e))

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
        exceeds_cap, counted = self._repo_scope_exceeds_cap(repo_path)
        if exceeds_cap:
            mgr.close()
            return ExecutionResult(
                success=False,
                planner="coding",
                goal=goal,
                confidence=0.0,
                observations=[
                    f"Repository at {repo_path} has more than {_ANALYZE_FILE_CAP:,} files "
                    f"(hit {counted:,}+ before stopping the count) — a full repo analysis "
                    "would be too slow to run inline.",
                    "Pass 'target_files' to analyze specific files instead, or point "
                    "'repository_path' at a smaller subdirectory.",
                ],
                data={
                    "backend": self.name,
                    "capability": "code.analyze",
                    "scope_truncated": True,
                    "file_count_estimate": counted,
                    "cap": _ANALYZE_FILE_CAP,
                    "repository_path": str(repo_path),
                },
            )

        try:
            analysis = mgr.analyze_repository()
            quality = mgr.get_quality_report()
            mgr.close()

            stats = analysis.get("statistics", {})
            repo_info = analysis.get("repository", {})
            file_count = stats.get("file_count", 0)
            folder_count = stats.get("folder_count", 0)
            issues_count = len(getattr(quality, "issues", []))
            language = repo_info.get("language", "unknown").title()

            return ExecutionResult(
                success=True,
                planner="coding",
                goal=goal,
                confidence=1.0,
                observations=[
                    f"Repository analysis complete: {repo_path.name}",
                    f"Files analyzed : {file_count:,}",
                    f"Folders        : {folder_count:,}",
                    f"Issues found   : {issues_count}",
                    f"Languages      : {language}",
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

    def _execute_edit(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        """
        Apply file edits using CodeEditor with validation and rollback.
        Requires edit_operations or (target_files + new_content) in arguments —
        or, failing that, a goal description agy can turn into edit_operations
        by inspecting the workspace itself.
        Returns real success/failure based on actual file write outcomes.
        """
        edit_operations: list[dict] = args.get("edit_operations", [])
        target_files: list[str] = args.get("target_files", [])
        new_content: str = args.get("new_content", "")

        # Build edit_operations from flat args if not provided as structured list
        if not edit_operations:
            file_path = args.get("file_path") or args.get("target_file")
            content = args.get("new_content") or args.get("content") or args.get("text")
            if file_path and content:
                edit_operations = [{"file_path": str(file_path), "new_content": str(content)}]
            elif target_files and new_content:
                edit_operations = [
                    {"file_path": f, "new_content": new_content}
                    for f in target_files
                ]

        agy_attempted = False
        if not edit_operations:
            # No explicit content given — ask agy to work out the edit from
            # the goal (and target_files, if given), by inspecting the real
            # repo via --add-dir. agy runs in --mode plan only: it returns
            # edit_operations, it never writes anything itself. Everything
            # it returns still goes through WorkspacePolicy below exactly
            # like explicitly-supplied edit_operations do.
            agy_attempted = True
            edit_goal = (
                f"Goal: {goal}\n"
                + (f"Target files: {target_files}\n" if target_files else "")
                + "Return ONLY a JSON object matching this schema, no markdown, no preamble: "
                  '{"edit_operations": [{"file_path": "relative/path.py", "new_content": "full corrected file content"}]}'
            )
            try:
                result = self.agy_client.run_plan(goal=edit_goal, add_dir=str(repo_path))
                edit_operations = result.raw.get("edit_operations", [])
            except AgyError as e:
                logger.warning("agy unavailable for code.edit goal inference (%s)", e)

        if not edit_operations:
            return ExecutionResult(
                success=False,
                planner="coding",
                goal=goal,
                confidence=0.0,
                observations=[
                    "File edit requires 'edit_operations' (list of {file_path, new_content}) "
                    "or 'target_files' + 'new_content' in arguments.",
                    (
                        "agy was asked to infer the edit from the goal description but "
                        "returned nothing usable (or was unavailable)."
                        if agy_attempted
                        else "No target_files/new_content given, so agy inference was not attempted."
                    ),
                ],
                data={"backend": self.name, "capability": "code.edit", "agy_attempted": agy_attempted},
            )

        return self._apply_edit_operations(goal, edit_operations, repo_path, capability="code.edit")

    def _execute_debug(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        """
        Diagnose and fix a bug using agy's workspace-aware reasoning, then
        apply the resulting edit_operations through the same
        WorkspacePolicy + CodeEditor path as _execute_edit.

        No Groq fallback here: debugging needs to actually inspect the
        workspace to find a root cause, which is exactly what agy's
        --add-dir gives us and blind Groq JSON generation never could.
        If agy is unavailable this returns an honest failure rather than
        guessing at a fix.
        """
        error_trace = args.get("error_trace") or args.get("traceback") or args.get("error") or ""
        target_files: list[str] = args.get("target_files", [])

        debug_goal = (
            f"Goal: {goal}\n"
            + (f"Error/traceback to fix:\n{error_trace}\n" if error_trace else "")
            + (f"Suspected files: {target_files}\n" if target_files else "")
            + "Inspect the workspace, find the root cause, and return ONLY a JSON "
              "object matching this schema, no markdown, no preamble: "
              '{"edit_operations": [{"file_path": "relative/path.py", "new_content": "full corrected file content"}]}'
        )

        try:
            result = self.agy_client.run_plan(goal=debug_goal, add_dir=str(repo_path))
        except AgyError as e:
            return self._error_result(
                goal, "code.debug",
                f"agy is unavailable ({e}). code.debug has no Groq fallback since it "
                "depends on workspace inspection to locate the root cause, which a "
                "blind JSON-generation call can't do reliably.",
            )

        edit_operations = result.raw.get("edit_operations", [])
        if not edit_operations:
            return self._error_result(
                goal, "code.debug", "agy inspected the workspace but returned no edit_operations."
            )

        return self._apply_edit_operations(goal, edit_operations, repo_path, capability="code.debug")

    def _apply_edit_operations(
        self, goal: str, edit_operations: list[dict], repo_path: Path, capability: str = "code.edit"
    ) -> ExecutionResult:
        """
        Shared apply path for _execute_edit and _execute_debug: every
        edit_operation — whatever produced it — goes through
        WorkspacePolicy.authorize_write() before CodeEditor touches disk.
        This is the single invariant-preserving gate M20.3 relies on.
        """
        try:
            from ....engineering.engineering_manager import EngineeringManager
        except (ImportError, ValueError):
            try:
                from engineering.engineering_manager import EngineeringManager
            except ImportError as e:
                import traceback
                tb = traceback.format_exc()
                return self._error_result(
                    goal, capability, f"EngineeringManager import failed: {e}\nTraceback:\n{tb}"
                )
            except Exception as e:
                return self._error_result(goal, capability, str(e))
        try:
            from .workspace_policy import WorkspacePolicy, WorkspacePolicyError
        except ImportError:
            pass # fallback if not found, but we should use it

        policy = WorkspacePolicy(repo_path)
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
            
            try:
                # Enforce WorkspacePolicy invariant on edit mutations
                policy.authorize_write(file_path_str, allow_overwrite=True)
            except WorkspacePolicyError as e:
                failed.append({"file": file_path_str, "error": f"Policy violation: {e}"})
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
        # Include policy violations + other failures in observations
        for f in failed:
            if "Policy violation" in f.get("error", ""):
                observations.append(f"Policy violation: {f['file']} — {f['error']}")
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
                "capability": capability,
                "modified_files": succeeded,
                "failed_files": [f["file"] for f in failed],
                "repository_path": str(repo_path),
            },
        )

    def _execute_report(
        self, goal: str, args: dict[str, Any], repo_path: Path
    ) -> ExecutionResult:
        """
        Generate a quality and dependency report for the repository.
        """
        try:
            from ....engineering.engineering_manager import EngineeringManager
        except (ImportError, ValueError):
            try:
                from engineering.engineering_manager import EngineeringManager
            except ImportError as e:
                import traceback
                tb = traceback.format_exc()
                return self._error_result(
                    goal, "code.report", f"EngineeringManager import failed: {e}\nTraceback:\n{tb}"
                )
            except Exception as e:
                return self._error_result(goal, "code.report", str(e))

        mgr = EngineeringManager(
            repository_path=repo_path,
            enable_lsp=False,
            enable_auto_sync=False,
        )

        exceeds_cap, counted = self._repo_scope_exceeds_cap(repo_path)
        if exceeds_cap:
            mgr.close()
            return ExecutionResult(
                success=False,
                planner="coding",
                goal=goal,
                confidence=0.0,
                observations=[
                    f"Repository at {repo_path} has more than {_ANALYZE_FILE_CAP:,} files "
                    f"(hit {counted:,}+ before stopping the count) — a full quality report "
                    "would be too slow to run inline.",
                    "Point 'repository_path' at a smaller subdirectory to get a report.",
                ],
                data={
                    "backend": self.name,
                    "capability": "code.report",
                    "scope_truncated": True,
                    "file_count_estimate": counted,
                    "cap": _ANALYZE_FILE_CAP,
                    "repository_path": str(repo_path),
                },
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
                f"Issues found: {getattr(report, 'total_issues', 'unknown')}",
                f"Quality score: {getattr(report, 'quality_score', 'unknown')}",
            ],
            data={
                "backend": self.name,
                "capability": "code.report",
                "report": getattr(report, "model_dump", lambda: report.__dict__)(),
                "repository_path": str(repo_path),
            },
        )

    # ── Private: helpers ───────────────────────────────────────────────────

    def _repo_scope_exceeds_cap(
        self, repo_path: Path, cap: int = _ANALYZE_FILE_CAP
    ) -> tuple[bool, int]:
        """
        Cheap directory walk to check whether repo_path is large enough that
        a full EngineeringManager.analyze_repository() / get_quality_report()
        pass would be slow. Stops counting the moment the count crosses `cap`
        — never walks the whole tree when it doesn't have to. Skips common
        non-source directories so a stray .venv/node_modules doesn't cause a
        false-positive truncation on an otherwise small project.

        Returns (exceeds_cap, count_so_far). count_so_far is a lower bound
        when exceeds_cap is True (counting stopped early), and exact when
        False.
        """
        import os

        count = 0
        for _dirpath, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [d for d in dirnames if d not in _ANALYZE_SCAN_SKIP_DIRS]
            count += len(filenames)
            if count > cap:
                return True, count
        return False, count

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
        generation_verbs = ["create", "generate", "build", "write", "implement", "develop", "make"]
        coding_nouns = ["code", "script", "app", "application", "database", "system", "program", "module", "function", "class"]
        
        goal_lower = goal.lower()
        has_verb = any(v in goal_lower for v in generation_verbs)
        has_noun = any(n in goal_lower for n in coding_nouns)
        
        has_signal = has_verb and has_noun
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
