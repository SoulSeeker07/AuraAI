import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser

parser = TypeScriptASTParser()
p = Path(".aura_staging/zustand_repo/src/middleware/persist.ts")
source_bytes = p.read_bytes()
file_path_str = str(p)

ts_parser, lang_name = parser._get_parser_and_lang(p)
print("1. Parsing tree ...", flush=True)
tree = ts_parser.parse(source_bytes)
print("2. Tree parsed, root:", tree.root_node.type, flush=True)

from engineering.language_providers.typescript.parser import ParsedTypeScriptFile
result = ParsedTypeScriptFile(file_path=file_path_str, language=lang_name)

root = tree.root_node
print("3. Visiting children one by one ...", flush=True)
for idx, child in enumerate(root.children):
    print(f"   [{idx}] Visiting child: {child.type} ...", flush=True)
    parser._visit_node(child, source_bytes, result, file_path_str, is_exported=False)
    print(f"       -> Total symbols so far: {len(result.symbols)}", flush=True)

print("4. Testing parse_source directly ...", flush=True)
res = parser.parse_source(source_bytes, p)
print(f"5. parse_source completed: {len(res.symbols)} symbols", flush=True)
