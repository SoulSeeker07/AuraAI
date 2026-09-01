import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser

parser = TypeScriptASTParser()
p = Path(".aura_staging/zustand_repo/src/react/shallow.ts")
source = p.read_bytes()

print("Testing parse_source on src/react/shallow.ts ...", flush=True)
res = parser.parse_source(source, p)
print(f"Done! Extracted {len(res.symbols)} symbols:")
for s in res.symbols:
    print(f"  {s.name} ({s.symbol_type}) -> tags: {s.tags}")
