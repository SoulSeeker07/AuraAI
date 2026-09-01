import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from engineering.language_providers.typescript.parser import TypeScriptASTParser

repo = Path(".aura_staging/zustand_repo").resolve()
parser = TypeScriptASTParser()

for idx, p in enumerate(sorted(repo.rglob("*")), 1):
    if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        print(f"[{idx}] Parsing {p.relative_to(repo)} ...", flush=True)
        content = p.read_bytes()
        res = parser.parse_source(content, p)
        print(f"    Done: {len(res.symbols)} symbols", flush=True)
