import sys
from pathlib import Path

for p in [str(Path(".").resolve() / "src"), str(Path(".").resolve())]:
    if p not in sys.path:
        sys.path.insert(0, p)

from engineering.project_index import ProjectIndex

print("Step 1: start")
repo = Path(".aura_staging/zustand_repo").resolve()
print("Step 2: repo =", repo)
db = repo / "test.sqlite3"
print("Step 3: db =", db)
idx = ProjectIndex(repo_root=repo, db_path=db)
print("Step 4: index created")
res = idx.scan()
print("Step 5: scan finished =", res)
