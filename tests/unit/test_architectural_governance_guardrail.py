"""
Architectural Governance Guardrail Tests
Location: tests/unit/test_architectural_governance_guardrail.py

Uses Python's AST parser to statically inspect the entire `src/` codebase and verify:
1. No backend adapter `.execute()`, `.execute_plan()`, `.execute_async()`, or
   `.execute_plan_async()` is invoked directly outside the canonical orchestrator
   chokepoints (`MasterOrchestrator._dispatch_plan` / `_dispatch_to_backend`).
2. No un-gated execution bypasses exist in `src/brain/` or `src/daemon/`.
3. Every registered capability in `CapabilityRegistry` has a valid, non-null risk tier.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import List, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

# Canonical files permitted to perform low-level backend adapter execution:
PERMITTED_BACKEND_EXECUTION_FILES = {
    # The canonical orchestrator chokepoint
    "src/core/orchestration/master_orchestrator.py",
    # Base backend interface delegation shim (BaseBackendAdapter.execute_plan delegating to self.execute)
    "src/core/backends/base_backend.py",
    # Backend registry fallback adapter delegating to concrete backend
    "src/core/backends/backend_registry.py",
    # Internal subprocess client wrapper
    "src/core/backends/adapters/agy_subprocess_client.py",
}

# Known backend class names whose methods must never be directly invoked for execution
BACKEND_CLASS_NAMES = {
    "DesktopBackend",
    "DesktopEngineBackend",
    "DesktopBackendAdapter",
    "SmartHomeBackendAdapter",
    "SmartHomeBackend",
    "CodeActBackendAdapter",
    "CodeActBackend",
    "BrowserBackendAdapter",
    "SecurityBackendAdapter",
    "TerminalBackendAdapter",
    "DaemonBackendAdapter",
    "PersonalOSBackendAdapter",
    "DockerBackendAdapter",
    "MCPBackendAdapter",
    "GroqBackendAdapter",
    "GeminiBackendAdapter",
}

TARGET_EXECUTION_METHODS = {
    "execute",
    "execute_async",
    "execute_plan",
    "execute_plan_async",
}


def _get_src_python_files() -> List[Path]:
    """Return all .py files in src/ excluding virtual environments or caches."""
    py_files = []
    for root, _, files in os.walk(SRC_DIR):
        if "__pycache__" in root or ".venv" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                py_files.append(Path(root) / file)
    return py_files


def _find_disallowed_backend_executions(file_path: Path) -> List[Tuple[int, str]]:
    """
    Parse a Python source file into an AST and find any disallowed direct
    calls to backend.execute / adapter.execute / Backend().execute.
    """
    rel_path = file_path.relative_to(PROJECT_ROOT).as_posix()
    if rel_path in PERMITTED_BACKEND_EXECUTION_FILES:
        return []

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        return []

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in TARGET_EXECUTION_METHODS:
                val = node.func.value
                is_backend_call = False

                # 1. Direct variable name: backend.execute / adapter.execute / backend_adapter.execute
                if isinstance(val, ast.Name) and val.id.lower() in (
                    "backend", "adapter", "backend_adapter", "desktop_backend", "smarthome_backend"
                ):
                    is_backend_call = True

                # 2. Instantiated class call: DesktopBackend().execute(...)
                elif isinstance(val, ast.Call) and isinstance(val.func, ast.Name) and val.func.id in BACKEND_CLASS_NAMES:
                    is_backend_call = True

                # 3. Attribute expression: self.backend.execute(...) / self.adapter.execute(...)
                elif isinstance(val, ast.Attribute) and val.attr.lower() in (
                    "backend", "adapter", "desktop_backend", "smarthome_backend"
                ):
                    is_backend_call = True

                if is_backend_call:
                    violations.append((
                        node.lineno,
                        f"Direct backend execution `.{attr_name}()` at line {node.lineno} in '{rel_path}'. "
                        f"Execution must route through `ExecutionPolicy` and `MasterOrchestrator._dispatch_plan`."
                    ))

    return violations


def test_ast_guardrail_no_unauthorized_backend_execution_outside_orchestrator():
    """
    AST Guardrail: Statically verifies that zero files outside the canonical
    orchestration chokepoint invoke backend execution methods directly.
    """
    all_files = _get_src_python_files()
    assert len(all_files) > 50, "Sanity check: Must scan a substantial number of Python files"

    all_violations = []
    for f in all_files:
        violations = _find_disallowed_backend_executions(f)
        all_violations.extend(violations)

    if all_violations:
        error_lines = "\n".join(f" - [L{line}] {msg}" for line, msg in all_violations)
        pytest.fail(
            f"Found {len(all_violations)} architectural governance violation(s) — direct backend execution outside MasterOrchestrator:\n"
            f"{error_lines}\n\n"
            f"Fix: Route execution through `ExecutionPolicy.evaluate_action()` and `MasterOrchestrator._dispatch_plan()`."
        )


def test_ast_guardrail_all_capabilities_have_valid_risk_classification():
    """
    Registry Guardrail: Verifies that every capability registered in CapabilityRegistry
    has an explicit, non-null ActionRisk classification.
    """
    from core.capabilities.capability_registry import CapabilityRegistry
    from core.orchestration.autonomy_mode import ActionRisk

    registry = CapabilityRegistry.get_instance()
    all_caps = registry.list()
    assert len(all_caps) >= 100, f"Expected at least 100 capabilities in registry, found {len(all_caps)}"

    unclassified = []
    for cap in all_caps:
        if not hasattr(cap, "risk_level") or cap.risk_level is None or not isinstance(cap.risk_level, ActionRisk):
            unclassified.append(cap.name if hasattr(cap, "name") else str(cap))

    assert len(unclassified) == 0, (
        f"Found {len(unclassified)} capability(ies) with missing/invalid ActionRisk: {unclassified[:10]}"
    )
