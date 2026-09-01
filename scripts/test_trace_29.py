import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser

ast_parser = TypeScriptASTParser()
repo = Path(".aura_staging/zustand_repo").resolve()
files = [p for p in sorted(repo.rglob("*")) if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")]

for idx in range(20, 36):
    p = files[idx]
    print(f"[{idx}] {p.relative_to(repo)} ...", flush=True)
    res = ast_parser.parse_source(p.read_bytes(), p)
    print(f"    Done: {len(res.symbols)} symbols", flush=True)
