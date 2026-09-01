import time
from pathlib import Path
from engineering.project_index import ProjectIndex

z_path = Path(".aura_staging/zustand_repo").resolve()
h_path = Path(".aura_staging/headlessui_repo").resolve()

# Clean staging databases
db_z = Path(".aura_staging/bench_z.sqlite3")
db_h = Path(".aura_staging/bench_h.sqlite3")
if db_z.exists():
    db_z.unlink()
if db_h.exists():
    db_h.unlink()

# Zustand
z_idx = ProjectIndex(repo_root=z_path, db_path=db_z)
t0 = time.perf_counter()
z_stats = z_idx.scan()
t1 = time.perf_counter()
z_cold_sec = t1 - t0
z_fps = z_stats["updated"] / z_cold_sec

t0 = time.perf_counter()
z_inc_stats = z_idx.scan()
t1 = time.perf_counter()
z_inc_ms = (t1 - t0) * 1000

# HeadlessUI
h_idx = ProjectIndex(repo_root=h_path, db_path=db_h)
t0 = time.perf_counter()
h_stats = h_idx.scan()
t1 = time.perf_counter()
h_cold_sec = t1 - t0
h_fps = h_stats["updated"] / h_cold_sec

t0 = time.perf_counter()
h_inc_stats = h_idx.scan()
t1 = time.perf_counter()
h_inc_ms = (t1 - t0) * 1000

print("=== REAL-WORLD CODEBASE BENCHMARKS ===")
print(f"Zustand ({z_stats['updated']} files):")
print(f"  Cold scan: {z_cold_sec:.3f}s ({z_fps:.1f} files/sec)")
print(f"  Incremental zero-drift: {z_inc_ms:.2f}ms")
print(f"HeadlessUI ({h_stats['updated']} files):")
print(f"  Cold scan: {h_cold_sec:.3f}s ({h_fps:.1f} files/sec)")
print(f"  Incremental zero-drift: {h_inc_ms:.2f}ms")
