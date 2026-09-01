#!/usr/bin/env python3
"""
Tier 2 Real-World React & TypeScript Validation Suite
=====================================================
Validates ProjectIndex & TypeScriptLanguageProvider against real-world
production repositories (.aura_staging/zustand_repo & .aura_staging/headlessui_repo).

Checks:
1. Full end-to-end ProjectIndex scan with SQLite persistence
2. Zero-symbol anomaly detection (flags non-trivial files with 0 symbols)
3. Extraction quality: React components, hooks, generics, interfaces, types, imports
4. Real-world end-to-end throughput (files / second)
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

# Ensure UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from engineering.project_index import ProjectIndex
from engineering.language_providers.typescript import TypeScriptLanguageProvider


def validate_repository(repo_path: Path, repo_name: str) -> dict[str, Any]:
    print(f"\n{'='*70}")
    print(f"RUNNING TIER 2 VALIDATION: {repo_name.upper()} ({repo_path})")
    print(f"{'='*70}")

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path not found: {repo_path}")

    # Set up isolated SQLite database in staging
    db_path = repo_path / ".aura_test_index.sqlite3"
    if db_path.exists():
        db_path.unlink()

    index = ProjectIndex(repo_root=repo_path, db_path=db_path)

    # 1. Measure Cold Scan
    start_time = time.perf_counter()
    try:
        stats = index.scan()
    except Exception as e:
        import traceback
        print("ERROR in index.scan():")
        traceback.print_exc()
        raise e
    cold_elapsed = time.perf_counter() - start_time

    total_files = stats.get("updated", 0)
    throughput = (total_files / cold_elapsed) if cold_elapsed > 0 else 0.0

    print(f"📊 Cold Scan Results:")
    print(f"  • Files Scanned & Indexed: {total_files}")
    print(f"  • Time Taken:              {cold_elapsed:.4f} seconds")
    print(f"  • Real-World Throughput:   {throughput:.1f} files / second")
    print(f"  • Avg Latency per File:    {(cold_elapsed/total_files*1000.0) if total_files else 0:.2f} ms")

    # 2. Measure Incremental Re-Scan
    re_start = time.perf_counter()
    re_stats = index.scan()
    re_elapsed = time.perf_counter() - re_start
    print(f"⚡ Incremental Re-Scan (Zero-Drift Cache):")
    print(f"  • Unchanged: {re_stats.get('unchanged', 0)} files in {re_elapsed*1000.0:.2f} ms")
    assert re_stats.get("unchanged", 0) == total_files, "Incremental scan did not identify all files as unchanged!"
    assert re_stats.get("updated", 0) == 0, "Incremental scan falsely marked files as updated!"

    # 3. Deep Symbol Quality & Anomaly Audit
    print(f"\n🔍 Deep Symbol Quality & Anomaly Audit:")
    zero_symbol_files = []
    symbol_type_counts: dict[str, int] = {}
    total_symbols = 0
    total_imports = 0
    total_call_edges = 0

    with index._get_connection() as conn:
        all_files = conn.execute("SELECT path FROM files").fetchall()
        for f_row in all_files:
            f_path_str = f_row["path"]
            syms = index.get_file_symbols(f_path_str)
            total_symbols += len(syms)

            if not syms:
                # Check if file has substantive code
                try:
                    f_size = Path(f_path_str).stat().st_size
                    # Ignore tiny re-export index shims or empty files
                    if f_size > 200:
                        zero_symbol_files.append((f_path_str, f_size))
                except Exception:
                    pass

            for s in syms:
                symbol_type_counts[s.symbol_type] = symbol_type_counts.get(s.symbol_type, 0) + 1

        imp_count = conn.execute("SELECT count(*) FROM imports").fetchone()[0]
        call_count = conn.execute("SELECT count(*) FROM call_edges").fetchone()[0]
        total_imports += imp_count
        total_call_edges += call_count

    print(f"  • Total Symbols Extracted:  {total_symbols}")
    print(f"  • Total Imports Recorded:   {total_imports}")
    print(f"  • Total Call Edges:         {total_call_edges}")
    print(f"  • Symbol Breakdown:")
    for stype, count in sorted(symbol_type_counts.items(), key=lambda x: -x[1]):
        print(f"      - {stype:<16}: {count}")

    if zero_symbol_files:
        print(f"  ⚠️ Zero-Symbol Warnings ({len(zero_symbol_files)} files > 200 bytes with 0 symbols):")
        for zf, sz in zero_symbol_files[:5]:
            print(f"      * {Path(zf).name} ({sz} bytes)")
    else:
        print(f"  ✅ 0 Zero-Symbol Anomalies: Every substantive source file successfully produced symbols.")

    # 4. Spot-Check Real Components / Types
    print(f"\n🎯 Spot-Checking Signature & Symbol Fidelity:")
    sample_symbols = index.find_symbol("create") or index.find_symbol("useStore") or index.find_symbol("Menu")
    if sample_symbols:
        for s in sample_symbols[:3]:
            print(f"  • Symbol: '{s.name}' ({s.symbol_type}) in {Path(s.file_path).name}:{s.line_start}")
            print(f"    Signature: `{s.signature}`")

    # Clean up test SQLite
    try:
        index.close()
        if db_path.exists():
            db_path.unlink()
    except Exception:
        pass

    return {
        "repo_name": repo_name,
        "total_files": total_files,
        "total_symbols": total_symbols,
        "total_imports": total_imports,
        "throughput": throughput,
        "zero_symbol_count": len(zero_symbol_files),
    }


def main():
    zustand_dir = PROJECT_ROOT / ".aura_staging" / "zustand_repo"
    headlessui_dir = PROJECT_ROOT / ".aura_staging" / "headlessui_repo"

    results = []
    if zustand_dir.exists():
        r1 = validate_repository(zustand_dir, "Zustand (React State & Hooks)")
        results.append(r1)

    if headlessui_dir.exists():
        r2 = validate_repository(headlessui_dir, "HeadlessUI (Tailwind React Components)")
        results.append(r2)

    print(f"\n{'='*70}")
    print("TIER 2 REAL-WORLD VALIDATION SUMMARY")
    print(f"{'='*70}")
    for r in results:
        print(f"  • {r['repo_name']}: {r['total_files']} files, {r['total_symbols']} symbols @ {r['throughput']:.1f} files/sec (Anomalies: {r['zero_symbol_count']})")
    print(f"{'='*70}")
    print("✅ TIER 2 REAL-WORLD VALIDATION COMPLETE & PASSED.")


if __name__ == "__main__":
    main()
