"""
Tier 2 Real-World React & TypeScript Validation Test Suite
==========================================================
Location: tests/engineering/test_tier2_real_repos.py

Runs live, full-repository indexing and symbol extraction against real-world
production React/TypeScript repositories:
- Zustand (React State Management, TypeScript Generics, Middleware)
- HeadlessUI (TailwindLabs React Component Library, JSX, ForwardRefs, Hooks)
"""

import time
from pathlib import Path
import pytest

from src.engineering.project_index import ProjectIndex
from src.engineering.symbol_graph import SymbolType


@pytest.fixture(scope="session")
def workspace_root():
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def zustand_path(workspace_root):
    return workspace_root / ".aura_staging" / "zustand_repo"


@pytest.fixture(scope="session")
def headlessui_path(workspace_root):
    return workspace_root / ".aura_staging" / "headlessui_repo"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Zustand Production Repository Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_zustand_real_world_indexing(zustand_path, tmp_path):
    if not zustand_path.exists():
        pytest.skip(f"Zustand repository not cloned at {zustand_path}")

    db_path = tmp_path / "zustand_index.sqlite3"
    index = ProjectIndex(repo_root=zustand_path, db_path=db_path)

    # 1. Cold Scan Performance
    start_t = time.perf_counter()
    stats = index.scan()
    elapsed = time.perf_counter() - start_t

    total_scanned = stats.get("updated", 0)
    assert total_scanned >= 20, f"Expected at least 20 source files in Zustand, got {total_scanned}"
    throughput = total_scanned / elapsed if elapsed > 0 else 0
    print(f"\n[Zustand] Cold scanned {total_scanned} files in {elapsed:.4f}s ({throughput:.1f} files/sec)")
    assert throughput > 100, f"Throughput {throughput} files/sec was lower than threshold 100"

    # 2. Incremental Zero-Drift Scan
    re_start = time.perf_counter()
    re_stats = index.scan()
    re_elapsed = time.perf_counter() - re_start
    assert re_stats.get("unchanged", 0) == total_scanned
    assert re_stats.get("updated", 0) == 0
    print(f"[Zustand] Incremental scan verified {re_stats['unchanged']} files in {re_elapsed*1000.0:.2f}ms")

    # 3. Symbol Fidelity & Generics
    use_store_syms = index.find_symbol("useStore")
    assert len(use_store_syms) >= 1
    sym = use_store_syms[0]
    assert sym.name == "useStore"
    assert sym.symbol_type == "function"

    create_syms = index.find_symbol("create")
    assert len(create_syms) >= 1

    # 4. Zero-Symbol Anomaly Audit
    with index._get_connection() as conn:
        all_files = conn.execute("SELECT path FROM files").fetchall()
        for f_row in all_files:
            f_path_str = f_row["path"]
            p = Path(f_path_str)
            syms = index.get_file_symbols(f_path_str)
            f_size = p.stat().st_size
            # If substantive (>300 bytes) and not a pure raw data string file or barrel re-export file
            is_barrel_or_resource = (
                "resources" in p.parts
                or p.name in ("middleware.ts", "index.ts", "shallow.ts", "vite-env.d.ts")
            )
            if f_size > 300 and not is_barrel_or_resource:
                assert len(syms) > 0, f"Silent zero-symbol drop in {p.name} ({f_size} bytes)"


# ─────────────────────────────────────────────────────────────────────────────
# 2. HeadlessUI Production Repository Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_headlessui_real_world_indexing(headlessui_path, tmp_path):
    if not headlessui_path.exists():
        pytest.skip(f"HeadlessUI repository not cloned at {headlessui_path}")

    db_path = tmp_path / "headlessui_index.sqlite3"
    index = ProjectIndex(repo_root=headlessui_path, db_path=db_path)

    # 1. Cold Scan Performance
    start_t = time.perf_counter()
    stats = index.scan()
    elapsed = time.perf_counter() - start_t

    total_scanned = stats.get("updated", 0)
    assert total_scanned >= 50, f"Expected at least 50 source files in HeadlessUI, got {total_scanned}"
    throughput = total_scanned / elapsed if elapsed > 0 else 0
    print(f"\n[HeadlessUI] Cold scanned {total_scanned} files in {elapsed:.4f}s ({throughput:.1f} files/sec)")

    # 2. Incremental Zero-Drift Scan
    re_stats = index.scan()
    assert re_stats.get("unchanged", 0) == total_scanned
    assert re_stats.get("updated", 0) == 0

    # 3. Component & Hook Extraction
    with index._get_connection() as conn:
        total_syms = conn.execute("SELECT count(*) FROM symbols").fetchone()[0]
        total_imps = conn.execute("SELECT count(*) FROM imports").fetchone()[0]
        total_calls = conn.execute("SELECT count(*) FROM call_edges").fetchone()[0]

        print(f"[HeadlessUI] Extracted {total_syms} symbols, {total_imps} imports, {total_calls} call edges")
        assert total_syms >= 100, f"Expected >= 100 symbols in HeadlessUI, got {total_syms}"
        assert total_imps >= 50, f"Expected >= 50 imports in HeadlessUI, got {total_imps}"
