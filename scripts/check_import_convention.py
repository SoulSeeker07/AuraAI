#!/usr/bin/env python3
"""
check_import_convention.py
==========================
CI/Pre-commit guard against the `src.*` import prefix split-singleton bug.

This project sets `pythonpath = ["src"]` in pyproject.toml, which means Python
can resolve `brain.X` and `src.brain.X` as **two different module keys** — even
though they resolve to the same physical file. Loading the same module under two
keys produces two separate class objects with two separate singleton `_instance`
slots, silently breaking all registry singletons (EngineRegistry,
DomainExpertRegistry, ExecutionPolicy, ...).

INVARIANT (frozen import convention):
    src/      -> STRICT: no `src.*` import prefixes
    tests/    -> STRICT: no `src.*` import prefixes
    scratch/  -> STRICT for active code; frozen M18-M23 historical acceptance
                 artifacts are exempt ONLY through the explicit
                 HISTORICAL_EXEMPT_ARTIFACTS allowlist (documented reasons,
                 never silent exclusions).
    All imports must use the bare path (e.g. `from brain.X import Y`, never
    `from src.brain.X import Y`).

Active Phase 6 gate scripts (H2/H3 in scratch/) follow the canonical bare-path
convention. Historical M18-M23 acceptance artifacts are intentionally frozen
and remain byte-for-byte/functionally unmodified.

Usage:
    python scripts/check_import_convention.py            # exits 0 if clean
    python scripts/check_import_convention.py --root DIR  # scan another root
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Patterns that indicate a forbidden `src.*` import prefix.
# NOTE: only the packages holding runtime singletons are guarded. If a new
# package introduces module-split-sensitive singletons, add it here.
FORBIDDEN_PATTERNS = [
    re.compile(r"^\s*(?:from|import)\s+src\.(brain|core|experts|autonomy|voice|vision)\b"),
]

# Directories to scan (repo-root relative)
SCAN_DIRS = ["src", "tests", "scratch"]

# File extensions to check
EXTENSIONS = {".py"}

# Files to exclude from scanning entirely
EXCLUDE_FILES = {"scripts/check_import_convention.py", "setup.py"}

# ---------------------------------------------------------------------------
# Frozen M18-M23 historical acceptance artifacts.
#
# These gate scripts were verified BEFORE the import-convention guard existed
# and are intentionally left byte-for-byte/functionally unmodified (their
# outputs are recorded acceptance evidence). They are exempt ONLY through this
# explicit, documented allowlist -- never silently. Removing or editing an
# entry requires an explicit architecture decision.
# ---------------------------------------------------------------------------
HISTORICAL_EXEMPT_ARTIFACTS: dict[str, str] = {
    "scratch/live_truth_pass.py": (
        "Historical pre-guard live-truth matrix acceptance artifact — frozen; "
        "verified before the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/m18_live_matrix.py": (
        "M18 live acceptance matrix artifact — frozen; verified before the "
        "import-convention guard; intentionally not retrofitted."
    ),
    "scratch/m19_live_matrix.py": (
        "M19 live acceptance matrix artifact — frozen; verified before the "
        "import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_m20_voice_continuity_gate.py": (
        "M20 voice-continuity acceptance gate artifact — frozen; verified before "
        "the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_cli_activity_trace.py": (
        "M20 CLI activity-trace acceptance artifact — frozen; verified before "
        "the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_notepad_stateful_edit.py": (
        "M21 stateful-edit acceptance artifact — frozen; verified before the "
        "import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_m21_desktop_manipulation_depth.py": (
        "M21 desktop-manipulation-depth acceptance gate artifact — frozen; "
        "verified before the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_youtube_adaptive_playback.py": (
        "M22 adaptive-playback acceptance artifact — frozen; verified before "
        "the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_facebook_adaptive_interaction.py": (
        "M22 adaptive-interaction acceptance artifact — frozen; verified before "
        "the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_m22_adaptive_recovery_gate.py": (
        "M22 adaptive-recovery acceptance gate artifact — frozen; verified "
        "before the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_m22_browser_adaptability.py": (
        "M22 browser-adaptability acceptance gate artifact — frozen; verified "
        "before the import-convention guard; intentionally not retrofitted."
    ),
    "scratch/test_m23_adversarial_robustness_gate.py": (
        "M23 adversarial-robustness acceptance gate artifact — frozen; verified "
        "before the import-convention guard; intentionally not retrofitted."
    ),
}


@dataclass
class ConventionScanResult:
    violation_count: int = 0
    violation_files: list[str] = field(default_factory=list)
    allowlisted_files: list[str] = field(default_factory=list)
    scanned_file_count: int = 0


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_no, line_content) for all forbidden imports in path."""
    violations = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return violations
    for lineno, line in enumerate(lines, start=1):
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.match(line):
                violations.append((lineno, line.rstrip()))
                break
    return violations


def scan_repository(repo_root: Path) -> ConventionScanResult:
    """Scan src/ + tests/ + scratch/ and report violations & allowlisted files."""
    result = ConventionScanResult()
    files: list[Path] = []
    for scan_dir in SCAN_DIRS:
        scan_path = repo_root / scan_dir
        if not scan_path.exists():
            continue
        for filepath in sorted(scan_path.rglob("*")):
            if filepath.suffix in EXTENSIONS:
                files.append(filepath)

    for filepath in files:
        rel = filepath.relative_to(repo_root)
        rel_str = str(rel).replace("\\", "/")
        if rel_str in EXCLUDE_FILES:
            continue
        if rel_str in HISTORICAL_EXEMPT_ARTIFACTS:
            result.allowlisted_files.append(rel_str)
            reason = HISTORICAL_EXEMPT_ARTIFACTS[rel_str]
            print(f"  [INFO]  ALLOWLISTED (frozen artifact): {rel_str}")
            print(f"          reason: {reason}")
            continue

        violations = scan_file(filepath)
        if violations:
            result.violation_files.append(rel_str)
            for lineno, line in violations:
                print(f"  VIOLATION  {rel_str}:{lineno}  ->  {line}")
                result.violation_count += 1

    result.scanned_file_count = len(files)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for forbidden src.* import prefixes.")
    parser.add_argument("--root", default=".", help="Repository root directory.")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    result = scan_repository(repo_root)

    print()
    if result.violation_count == 0:
        print(
            f"[PASS]  Import convention check PASSED -- no forbidden `src.*` import "
            f"prefixes found across {result.scanned_file_count} file(s); "
            f"{len(result.allowlisted_files)} frozen artifact(s) allowlisted."
        )
        return 0

    print(
        f"[FAIL]  Import convention check FAILED -- {result.violation_count} "
        f"violation(s) in {len(result.violation_files)} file(s)."
    )
    print()
    print("ROOT CAUSE: With `pythonpath = [\"src\"]` in pyproject.toml, importing")
    print("`src.brain.X` and `brain.X` loads the SAME FILE under TWO module keys,")
    print("producing two separate singleton instances and silently breaking all registries.")
    print()
    print("FIX: Replace `from src.brain.*`, `from src.core.*`, `from src.experts.*`,")
    print("     `from src.autonomy.*` with their bare equivalents: `from brain.*`, etc.")
    print("     Frozen M18-M23 artifacts may be allowlisted WITH a documented reason;")
    print("     removing an allowlist entry requires an architecture decision.")
    return 1


if __name__ == "__main__":
    sys.exit(main())