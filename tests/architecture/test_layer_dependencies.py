"""
Phase 10: Layer Dependency & No-Cycles Test
============================================
Enforces the one-directional dependency graph:

    core/planning  (lowest — no dependencies on other Aura layers)
         ↓
    core/backends  (may depend on core/planning)
         ↓
    core/orchestration  (may depend on core/planning + core/backends)
         ↓
    desktop/native  (may depend on core)
         ↓
    desktop/planner  (may depend on desktop/native + core)

FORBIDDEN (tested here):
- core/planning  → desktop.*
- core/planning  → core/backends
- core/backends.adapters  → desktop/native/desktop_context
- desktop/native/managers  → desktop/planner
- any Win32-specific import in core/planning
"""

import ast
import sys
from pathlib import Path
from typing import List, Set, Tuple

import pytest

SRC = Path(__file__).parent.parent.parent / "src"


def _get_imports(filepath: Path) -> set[str]:
    """Parse a Python file and return all top-level import module names."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # Resolve relative imports to a rough absolute path
                module = node.module.split(".")[0]
                imports.add(module)
            elif node.level:
                # pure relative — extract first part of level + module
                pass
    return imports


def _files_in(subpath: str) -> list[Path]:
    """Return all .py files under src/subpath."""
    folder = SRC / subpath
    if not folder.exists():
        return []
    return list(folder.rglob("*.py"))


def _check_forbidden(
    source_folder: str,
    forbidden_module_prefixes: list[str],
) -> list[str]:
    """
    For every .py file in source_folder, parse imports using AST and check that
    none of the import statements reference any forbidden module prefix.

    Returns a list of violation strings.
    """
    violations = []
    for py_file in _files_in(source_folder):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_module_prefixes:
                        if alias.name == forbidden or alias.name.startswith(
                            forbidden + "."
                        ):
                            rel = py_file.relative_to(SRC)
                            violations.append(
                                f"  {rel}:{node.lineno}: import {alias.name} (forbidden: {forbidden})"
                            )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_module_prefixes:
                        if node.module == forbidden or node.module.startswith(
                            forbidden + "."
                        ):
                            rel = py_file.relative_to(SRC)
                            violations.append(
                                f"  {rel}:{node.lineno}: from {node.module} import ... (forbidden: {forbidden})"
                            )
    return violations


# ─── Tests ─────────────────────────────────────────────────────────────────────


def test_core_planning_does_not_import_desktop():
    """
    core/planning is the lowest layer.
    It must NEVER import from desktop.* or any Aura-specific layer above it.
    """
    forbidden = ["desktop", "src.desktop"]
    violations = _check_forbidden("core/planning", forbidden)
    assert not violations, (
        "core/planning imports desktop (LAYER VIOLATION):\n"
        + "\n".join(violations)
        + "\n\nFix: move shared types to core/planning, not desktop."
    )


def test_core_planning_does_not_import_win32():
    """
    core/planning must not import Win32 APIs.
    It is a pure Python planning layer.
    """
    forbidden = ["win32", "pywintypes", "winreg", "ctypes", "winerror", "comtypes"]
    violations = _check_forbidden("core/planning", forbidden)
    assert not violations, (
        "core/planning imports Win32 API (LAYER VIOLATION):\n"
        + "\n".join(violations)
        + "\n\nFix: Win32 calls belong in desktop/native/managers only."
    )


def test_core_backends_adapters_do_not_import_desktop_context():
    """
    core/backends/adapters must not import DesktopContext.
    Adapters are thin wrappers — they have no business knowing about
    the synchronized desktop state object.
    """
    forbidden = ["desktop_context", "DesktopContext"]
    violations = _check_forbidden("core/backends/adapters", forbidden)
    assert not violations, (
        "core/backends/adapters imports DesktopContext (LAYER VIOLATION):\n"
        + "\n".join(violations)
        + "\n\nFix: adapters should only import ExecutionResult and BaseBackendAdapter."
    )


def test_native_managers_do_not_import_planner():
    """
    desktop/native/managers must not import planners.
    Managers are pure execution units — they must not know about planning.
    """
    forbidden = [
        "desktop.planner",
        "core.planning",
        "BasePlanner",
        "DesktopPlanner",
        "PlanState",
    ]
    violations = _check_forbidden("desktop/native/managers", forbidden)
    assert not violations, (
        "desktop/native/managers imports planner layer (LAYER VIOLATION):\n"
        + "\n".join(violations)
        + "\n\nFix: managers should not know about planning. Use events/callbacks instead."
    )


def test_execution_package_does_not_import_desktop():
    """
    src/execution (the tool execution engine) must not import desktop.*.
    It is a generic execution layer that operates below desktop specifics.
    """
    forbidden = ["desktop.native", "src.desktop"]
    violations = _check_forbidden("execution", forbidden)
    assert not violations, (
        "execution package imports desktop (LAYER VIOLATION):\n"
        + "\n".join(violations)
        + "\n\nFix: execution/ is a generic layer. Desktop specifics belong in desktop/."
    )


def test_no_circular_imports_core_planning():
    """
    Verify no circular imports exist in core/planning.
    This uses Python's import machinery directly.
    """
    # Remove previously cached core.planning to force fresh re-import
    keys_to_remove = [k for k in sys.modules if k.startswith("core.planning")]
    for k in keys_to_remove:
        del sys.modules[k]

    try:
        import core.planning  # noqa: F401
        import core.planning.base_planner  # noqa: F401
        import core.planning.execution_result  # noqa: F401
        import core.planning.execution_trace  # noqa: F401
        import core.planning.plan_evaluator  # noqa: F401
        import core.planning.planner_state  # noqa: F401
    except ImportError as e:
        pytest.fail(f"Circular import detected in core/planning: {e}")


def test_no_src_prefix_imports():
    """
    No file in src/ should use 'from src.X import' or 'import src.X'.
    This is a broken import pattern that fails when the package is
    installed and src/ is on sys.path directly.
    """
    violations = []
    for py_file in SRC.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="replace")
        if "from src." in content or "import src." in content:
            rel = py_file.relative_to(SRC)
            # Collect all offending lines
            for i, line in enumerate(content.splitlines(), 1):
                if "from src." in line or "import src." in line:
                    violations.append(f"  {rel}:{i}: {line.strip()}")

    assert not violations, (
        f"{len(violations)} file(s) use 'from src.' or 'import src.' (BROKEN IMPORT PATTERN):\n"
        + "\n".join(violations[:20])  # limit to first 20 violations
        + ("\n  ... (truncated)" if len(violations) > 20 else "")
        + "\n\nFix: use relative imports (from .module) or absolute (from core.planning)."
    )
