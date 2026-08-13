"""
Architecture Guardrail — Import Convention (split-singleton protection)
========================================================================

Enforces the permanent `src.`-free import convention established alongside
`pythonpath = ["src"]` in pyproject.toml.

Background:
    Loading the same physical module under `brain.X` and `src.brain.X` produces
    TWO separate class objects with TWO separate singleton `_instance` slots,
    silently breaking EngineRegistry / DomainExpertRegistry / ExecutionPolicy
    and all runtime registries.

Scope (frozen Phase-6 convention):
    - STRICT: src/ and tests/ — zero `src.*` import prefixes.
    - STRICT: active scratch code (incl. H2/H3/H4 Phase-6 gates) — bare paths.
    - Exempt: frozen M18-M23 historical acceptance artifacts ONLY via the
      explicit, documented HISTORICAL_EXEMPT_ARTIFACTS allowlist in
      scripts/check_import_convention.py. Exemptions are never silent.

This test mirrors the AST-guardrail style of test_guardrails.py and runs under
`pytest tests/architecture` in CI.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    checker_path = ROOT / "scripts" / "check_import_convention.py"
    spec = importlib.util.spec_from_file_location("check_import_convention", checker_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_import_convention"] = module
    spec.loader.exec_module(module)
    return module


def test_import_convention_has_zero_violations():
    """
    No file in src/, tests/, or active scratch code may import `src.*` for the
    singleton-holding packages (brain, core, experts, autonomy, voice, vision).
    """
    checker = _load_checker()
    result = checker.scan_repository(ROOT)

    assert result.violation_count == 0, (
        "Forbidden `src.*` import prefixes found in "
        f"{len(result.violation_files)} file(s):\n"
        + "\n".join(f"  {f}" for f in result.violation_files)
        + "\n\nWith `pythonpath = [\"src\"]`, `src.brain.X` and `brain.X` load the "
        "SAME file under TWO module keys, splitting singleton registries. Convert "
        "the imports to the bare path (e.g. `from brain.X import Y`) or add an "
        "explicit allowlist entry with a documented reason."
    )


def test_import_convention_allowlist_is_exact_and_documented():
    """
    The set of allowlisted files encountered on disk must exactly match the
    documented HISTORICAL_EXEMPT_ARTIFACTS entries (no stale, missing, or
    undocumented exemptions). Every allowlist reason must be non-empty.
    """
    checker = _load_checker()
    result = checker.scan_repository(ROOT)

    expected = sorted(
        rel for rel in checker.HISTORICAL_EXEMPT_ARTIFACTS if (ROOT / rel).exists()
    )
    assert sorted(result.allowlisted_files) == expected, (
        "Allowlist mismatch. Expected on-disk exemptions:\n  "
        + "\n  ".join(expected or ["(none)"])
        + "\nEncountered:\n  "
        + "\n  ".join(sorted(result.allowlisted_files) or ["(none)"])
        + "\n\nEvery historical exemption must be documented in "
        "HISTORICAL_EXEMPT_ARTIFACTS; every documented entry must correspond to "
        "a real file. Stale or undeclared exemptions are rejected."
    )

    for rel, reason in checker.HISTORICAL_EXEMPT_ARTIFACTS.items():
        assert reason and reason.strip(), f"Allowlist entry '{rel}' has an empty reason."
