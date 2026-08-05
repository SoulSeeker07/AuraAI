"""
Repository Reorganization & Cleanup Script
===========================================
Executes file moves to clean up the root directory and organize files into:
- tests/desktop/
- scripts/
- logs/
- docs/milestones/
- developer/experiments/
"""

import shutil
import sys
from pathlib import Path

# Configure stdout to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories to ensure exist
DIRS_TO_CREATE = [
    PROJECT_ROOT / "developer",
    PROJECT_ROOT / "developer" / "benchmarks",
    PROJECT_ROOT / "developer" / "profiling",
    PROJECT_ROOT / "developer" / "experiments",
    PROJECT_ROOT / "developer" / "migration",
    PROJECT_ROOT / "developer" / "release_notes",
    PROJECT_ROOT / "temp",
    PROJECT_ROOT / "logs",
    PROJECT_ROOT / "docs" / "milestones",
    PROJECT_ROOT / "tests" / "desktop",
]

# File move map: (source, destination)
MOVES = [
    (
        PROJECT_ROOT / "test_permission_manager.py",
        PROJECT_ROOT / "tests" / "desktop" / "test_permission_manager.py",
    ),
    (
        PROJECT_ROOT / "test_process_events.py",
        PROJECT_ROOT / "tests" / "desktop" / "test_process_events.py",
    ),
    (
        PROJECT_ROOT / "test_process_manager.py",
        PROJECT_ROOT / "tests" / "desktop" / "test_process_manager.py",
    ),
    (PROJECT_ROOT / "update_disc.py", PROJECT_ROOT / "scripts" / "update_disc.py"),
    (PROJECT_ROOT / "update_reg.py", PROJECT_ROOT / "scripts" / "update_reg.py"),
    (
        PROJECT_ROOT / "research_test_output.log",
        PROJECT_ROOT / "logs" / "research_test_output.log",
    ),
    (
        PROJECT_ROOT / "research_timing_complete.log",
        PROJECT_ROOT / "logs" / "research_timing_complete.log",
    ),
    (
        PROJECT_ROOT / "research_timing_final.log",
        PROJECT_ROOT / "logs" / "research_timing_final.log",
    ),
    (
        PROJECT_ROOT / "research_timing_output.log",
        PROJECT_ROOT / "logs" / "research_timing_output.log",
    ),
    (
        PROJECT_ROOT / "research_timing_output_v2.log",
        PROJECT_ROOT / "logs" / "research_timing_output_v2.log",
    ),
    (PROJECT_ROOT / "configs", PROJECT_ROOT / "developer" / "experiments" / "configs"),
    (PROJECT_ROOT / "d", PROJECT_ROOT / "developer" / "experiments" / "d"),
    (
        PROJECT_ROOT / "docs" / "MILESTONE_15_PHASE1_COMPLETE.md",
        PROJECT_ROOT / "docs" / "milestones" / "MILESTONE_15_PHASE1_COMPLETE.md",
    ),
    (
        PROJECT_ROOT / "docs" / "MILESTONE_15_PHASE1_IMPROVEMENTS_COMPLETE.md",
        PROJECT_ROOT
        / "docs"
        / "milestones"
        / "MILESTONE_15_PHASE1_IMPROVEMENTS_COMPLETE.md",
    ),
    (
        PROJECT_ROOT / "docs" / "PHASE2_COMPLETE.md",
        PROJECT_ROOT / "docs" / "milestones" / "PHASE2_COMPLETE.md",
    ),
    (
        PROJECT_ROOT / "docs" / "PHASE2_SINGLETON_PLAN.md",
        PROJECT_ROOT / "docs" / "milestones" / "PHASE2_SINGLETON_PLAN.md",
    ),
]


def main():
    print("Creating directories...")
    for d in DIRS_TO_CREATE:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {d.relative_to(PROJECT_ROOT)}")

    print("\nMoving files...")
    moved_count = 0
    for src, dest in MOVES:
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            print(f"  [OK] {src.name} -> {dest.relative_to(PROJECT_ROOT)}")
            moved_count += 1
        else:
            print(f"  [SKIP] Not found: {src.name}")

    print(f"\nCompleted: Moved {moved_count} files successfully.")


if __name__ == "__main__":
    main()
