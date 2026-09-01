import sys
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_typescript as tst

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from engineering.language_providers.typescript.parser import TypeScriptASTParser

lang = Language(tst.language_typescript())
parser = Parser(lang)
ast_parser = TypeScriptASTParser()

p = Path(".aura_staging/zustand_repo/src/middleware/persist.ts")
content = p.read_bytes()
tree = parser.parse(content)

print("Now parsing entire persist.ts with parse_source ...", flush=True)
res = ast_parser.parse_source(content, p)
print(f"Full persist.ts parsed: {len(res.symbols)} symbols, {len(res.imports)} imports, {len(res.call_edges)} call edges", flush=True)
