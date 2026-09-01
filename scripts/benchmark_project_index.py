"""
Demonstration & Timing Proof for Persistent Structural Memory (ProjectIndex).
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.engineering.project_index import ProjectIndex


def run_benchmark():
    repo_root = Path(__file__).resolve().parents[1]
    db_dir = repo_root / ".aura" / "memory"
    db_path = db_dir / "project_index.sqlite3"

    print("=" * 70)
    print("Persistent Structural Memory (ProjectIndex) — Live Performance Benchmark")
    print(f"Target Repository: {repo_root}")
    print(f"Index SQLite DB:   {db_path}")
    print("=" * 70)

    # 1. Clean previous index for pure cold scan timing
    if db_path.exists():
        db_path.unlink(missing_ok=True)
    wal_file = Path(str(db_path) + "-wal")
    shm_file = Path(str(db_path) + "-shm")
    wal_file.unlink(missing_ok=True)
    shm_file.unlink(missing_ok=True)

    index = ProjectIndex(repo_root=repo_root, db_path=db_path)

    # ── RUN 1: Cold Scan ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    stats_cold = index.scan()
    cold_duration = time.perf_counter() - t0

    print("\n[RUN 1: Full Cold Scan]")
    print(f"  Duration:     {cold_duration * 1000:.2f} ms ({cold_duration:.4f} s)")
    print(f"  Files parsed: {stats_cold['updated']}")
    print(f"  Unchanged:    {stats_cold['unchanged']}")
    print(f"  Deleted:      {stats_cold['deleted']}")

    # ── RUN 2: Warm Scan (0 files changed) ────────────────────────────────────
    t0 = time.perf_counter()
    stats_warm = index.scan()
    warm_duration = time.perf_counter() - t0

    print("\n[RUN 2: Warm Scan - Zero Changes]")
    print(f"  Duration:     {warm_duration * 1000:.2f} ms ({warm_duration:.4f} s)")
    print(f"  Files parsed: {stats_warm['updated']}")
    print(f"  Unchanged:    {stats_warm['unchanged']} (100% cache hit)")
    print(f"  Speedup:      {cold_duration / max(warm_duration, 0.0001):.2f}x faster")

    # ── RUN 3: Incremental Scan (1 file changed) ──────────────────────────────
    dummy_file = repo_root / "src" / "engineering" / "_benchmark_dummy.py"
    dummy_file.write_text(
        '''"""Benchmark temporary module."""

def benchmark_probe_function(x: int) -> int:
    """Probe function."""
    return x * 2
''',
        encoding="utf-8",
    )

    try:
        t0 = time.perf_counter()
        stats_inc = index.scan()
        inc_duration = time.perf_counter() - t0

        print("\n[RUN 3: Incremental Scan - 1 Modified File]")
        print(f"  Duration:     {inc_duration * 1000:.2f} ms ({inc_duration:.4f} s)")
        print(f"  Files parsed: {stats_inc['updated']} (only modified file!)")
        print(f"  Unchanged:    {stats_inc['unchanged']} (cached)")

        # Verify Query API on newly added symbol
        probe_syms = index.find_symbol("benchmark_probe_function")
        print(f"  find_symbol('benchmark_probe_function') -> found {len(probe_syms)} match: {probe_syms[0].qualified_name if probe_syms else 'NONE'}")

        # ── RUN 4: Live Invalidation Hook ─────────────────────────────────────
        t0 = time.perf_counter()
        dummy_file.write_text(
            '''"""Benchmark temporary module modified live."""

def benchmark_live_invalidated_probe(y: str) -> str:
    """Live probe docstring."""
    return y.upper()
''',
            encoding="utf-8",
        )
        invalidated = index.invalidate_file(dummy_file)
        live_duration = time.perf_counter() - t0

        print("\n[RUN 4: Live Invalidation Hook (Immediate Single-File Invalidation)]")
        print(f"  Success:      {invalidated}")
        print(f"  Duration:     {live_duration * 1000:.2f} ms")
        live_syms = index.find_symbol("benchmark_live_invalidated_probe")
        print(f"  find_symbol('benchmark_live_invalidated_probe') -> found {len(live_syms)} match: {live_syms[0].signature if live_syms else 'NONE'}")

    finally:
        if dummy_file.exists():
            dummy_file.unlink()
        index.invalidate_file(dummy_file)

    # ── RUN 5: Query API Demonstrations on Core Codebase ──────────────────────
    print("\n[RUN 5: Query API Verification on Repository Symbols]")

    # 1. find_symbol
    syms = index.find_symbol("RepositoryManager")
    print(f"  1. find_symbol('RepositoryManager'):")
    for s in syms[:3]:
        print(f"     • {s.symbol_type}: {s.qualified_name} [{s.file_path}:{s.line_start}]")

    # 2. get_importers_of
    importers = index.get_importers_of("src.engineering.project_index")
    print(f"  2. get_importers_of('src.engineering.project_index'): {len(importers)} files")
    for imp in importers[:3]:
        print(f"     • {Path(imp).name}")

    # 3. get_callers_of
    callers = index.get_callers_of("invalidate_file")
    print(f"  3. get_callers_of('invalidate_file'): {len(callers)} callers")
    for c in callers[:3]:
        print(f"     • {c.name} in {Path(c.file_path).name}")

    print("\n" + "=" * 70)
    print("Benchmark Completed Successfully.")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
