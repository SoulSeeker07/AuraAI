import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser

ast_parser = TypeScriptASTParser()
repo = Path(".aura_staging/zustand_repo").resolve()
p_devtools = repo / "src" / "middleware" / "devtools.ts"
p_immer = repo / "src" / "middleware" / "immer.ts"

print("1. Parsing devtools.ts ...", flush=True)
r1 = ast_parser.parse_source(p_devtools.read_bytes(), p_devtools)
print(f"   Done devtools.ts: {len(r1.symbols)} symbols", flush=True)

print("2. Parsing immer.ts ...", flush=True)
r2 = ast_parser.parse_source(p_immer.read_bytes(), p_immer)
print(f"   Done immer.ts: {len(r2.symbols)} symbols", flush=True)
