import sys
from pathlib import Path
import traceback

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.project_index import ProjectIndex

repo = Path(".aura_staging/zustand_repo").resolve()
db = repo / "test_devtools.sqlite3"
if db.exists(): db.unlink()

idx = ProjectIndex(repo_root=repo, db_path=db)
f = repo / "src" / "middleware" / "devtools.ts"

content = f.read_bytes()
mtime = f.stat().st_mtime
chash = idx._compute_hash(content)

with idx._get_connection() as conn:
    try:
        ok = idx._parse_and_upsert(conn, f, content, mtime, chash)
        print("Upsert ok:", ok)
    except Exception:
        traceback.print_exc()

# If devtools succeeded, let's test all files in zustand sequentially
for idx_num, p in enumerate(sorted(repo.rglob("*")), 1):
    if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        content = p.read_bytes()
        mtime = p.stat().st_mtime
        chash = idx._compute_hash(content)
        with idx._get_connection() as conn:
            try:
                ok = idx._parse_and_upsert(conn, p, content, mtime, chash)
                conn.commit()
                print(f"[{idx_num}] OK: {p.name}")
            except Exception as e:
                print(f"[{idx_num}] FAILED: {p.name}: {e}")
