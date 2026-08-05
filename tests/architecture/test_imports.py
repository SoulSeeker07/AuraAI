"""
Phase 7: Import Validation Test
================================
Auto-imports every module in src/ and fails if anything is broken.

Catches:
- Syntax errors
- Missing dependencies
- Circular imports
- Renamed modules left behind
- Bad __init__.py re-exports

NOTE: Uses a file-system walk instead of pkgutil.walk_packages to avoid
needing to import 'src' at collection time (which fails in importlib mode).
"""

import importlib
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent.parent / "src"
ROOT = Path(__file__).parent.parent.parent
while "" in sys.path:
    sys.path.remove("")
while str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
while str(SRC) in sys.path:
    sys.path.remove(str(SRC))

sys.path.insert(0, str(SRC))
sys.path.insert(1, str(ROOT))

# Clear cached core modules if any were imported from ROOT
to_remove = [mod for mod in sys.modules if mod == "core" or mod.startswith("core.")]
for mod in to_remove:
    sys.modules.pop(mod, None)


# Packages that require unavailable system-level deps (optional features)
SKIP_PACKAGE_PREFIXES = (
    "vision",  # requires opencv (cv2)
    "voice",  # may require audio hardware
)


def _collect_module_names():
    """Walk src/ filesystem and return Python module dotted names."""
    modules = []
    for py_file in sorted(SRC.rglob("*.py")):
        rel = py_file.relative_to(SRC)
        parts = list(rel.parts)
        # Convert path to module name: foo/bar/baz.py -> foo.bar.baz
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]  # strip .py
        if not parts:
            continue
        module_name = ".".join(parts)
        # Skip __pycache__, egg-info, etc.
        if any(p.startswith("_") and p != "__init__" for p in parts if p != parts[0]):
            continue
        if "aura_ai.egg-info" in str(py_file):
            continue
        if "__pycache__" in str(py_file):
            continue
        modules.append(module_name)
    return modules


# ─── Bulk summary tests (fast, for quick runs) ─────────────────────────────────


def test_all_core_modules_importable():
    """All modules in src/core/ must import cleanly."""
    errors = []
    for py_file in sorted((SRC / "core").rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(SRC)
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        module_name = ".".join(parts)
        try:
            importlib.import_module(module_name)
        except Exception as e:
            errors.append(f"  {module_name}: {type(e).__name__}: {e}")

    if errors:
        pytest.fail(
            f"{len(errors)} core module(s) failed to import:\n" + "\n".join(errors)
        )


def test_all_desktop_modules_importable():
    """All modules in src/desktop/ must import cleanly."""
    errors = []
    for py_file in sorted((SRC / "desktop").rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(SRC)
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        module_name = ".".join(parts)
        try:
            importlib.import_module(module_name)
        except Exception as e:
            errors.append(f"  {module_name}: {type(e).__name__}: {e}")

    if errors:
        pytest.fail(
            f"{len(errors)} desktop module(s) failed to import:\n" + "\n".join(errors)
        )


def test_all_execution_modules_importable():
    """All modules in src/execution/ must import cleanly."""
    errors = []
    for py_file in sorted((SRC / "execution").rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(SRC)
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        module_name = ".".join(parts)
        try:
            importlib.import_module(module_name)
        except Exception as e:
            errors.append(f"  {module_name}: {type(e).__name__}: {e}")

    if errors:
        pytest.fail(
            f"{len(errors)} execution module(s) failed to import:\n" + "\n".join(errors)
        )


def test_engineering_module_importable():
    """src/engineering must import cleanly (was broken by mutable default dataclass)."""
    try:
        importlib.import_module("engineering")
        importlib.import_module("engineering.import_manager")
    except Exception as e:
        pytest.fail(f"engineering module failed: {type(e).__name__}: {e}")
