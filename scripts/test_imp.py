import sys
print("Hello before import")
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
print("sys.path updated:", sys.path[:2])
import engineering.project_index
from engineering.project_index import ProjectIndex

print("Creating ProjectIndex...")
repo = Path(".aura_staging/zustand_repo").resolve()
db = repo / "test.sqlite3"
if db.exists(): db.unlink()

idx = ProjectIndex(repo_root=repo, db_path=db)
print("ProjectIndex initialized.")

import os

SUPPORTED_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
IGNORED_DIRS = {'.venv', 'venv', 'env', '.git', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', 'node_modules', 'build', 'dist', '.aura_backups', '.staging', 'artifacts'}

disk_files = []
for dirpath, dirnames, filenames in os.walk(str(repo)):
    dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
    for fname in filenames:
        ext = Path(fname).suffix.lower()
        if ext in SUPPORTED_EXTENSIONS:
            disk_files.append(Path(dirpath) / fname)

print(f"Total files to scan: {len(disk_files)}")

with idx._get_connection() as conn:
    for idx_num, f in enumerate(disk_files, 1):
        print(f"[{idx_num}/{len(disk_files)}] Parsing: {f.name} ...", flush=True)
        content = f.read_bytes()
        mtime = f.stat().st_mtime
        chash = idx._compute_hash(content)
        ok = idx._parse_and_upsert(conn, f, content, mtime, chash)
        if not ok:
            print(f"  FAILED to parse: {f.name}", flush=True)
    conn.commit()

print("ALL FILES PARSED SUCCESSFULLY!")
