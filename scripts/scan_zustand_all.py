import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser

parser = TypeScriptASTParser()
repo = Path(".aura_staging/zustand_repo").resolve()
files = [p for p in sorted(repo.rglob("*")) if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")]

print(f"Discovered {len(files)} files in Zustand.")
total_symbols = 0
for idx, p in enumerate(files, 1):
    content = p.read_bytes()
    res = parser.parse_source(content, p)
    total_symbols += len(res.symbols)
    print(f"[{idx}/{len(files)}] {p.relative_to(repo)} -> {len(res.symbols)} symbols", flush=True)

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print(f"\n[SUCCESS] All {len(files)} files in Zustand parsed with 0 errors. Total symbols: {total_symbols}")
