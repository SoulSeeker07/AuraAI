import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from src.engineering.project_index import ProjectIndex
    print("ProjectIndex imported successfully")
except Exception as e:
    print("Import error:")
    traceback.print_exc()
    sys.exit(1)

root = (PROJECT_ROOT / ".aura_staging" / "zustand_repo").resolve()
print("Scanning:", root)
for f in sorted(root.rglob("*")):
    if f.is_file() and f.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            symbols, imports, calls = ProjectIndex._extract_file_data(None, str(f), content)
            print(f"  OK: {f.name} -> {len(symbols)} symbols, {len(imports)} imports, {len(calls)} calls")
        except Exception as e:
            print(f"  FAILED: {f.name} -> {e}")
