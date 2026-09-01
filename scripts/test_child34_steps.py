import gc
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser, ParsedTypeScriptFile

ast_parser = TypeScriptASTParser()
p = Path(".aura_staging/zustand_repo/src/middleware/devtools.ts")
content = p.read_bytes()
parser, _ = ast_parser._get_parser_and_lang(p)
tree = parser.parse(content)
root = tree.root_node
c34 = root.named_child(34)
decl = c34.named_child(0)
name_node = decl.child_by_field_name("name")
value_node = decl.child_by_field_name("value")

print("Step 1: Extract params & return type...", flush=True)
params, ret = ast_parser._extract_params_and_return_type(value_node, content)
print(f"  Params: {params}, Ret: {ret}", flush=True)
gc.collect()
print("Step 1 GC OK!", flush=True)

print("Step 2: Extract docstring...", flush=True)
doc = ast_parser._extract_leading_docstring(c34, content)
print(f"  Doc: {doc}", flush=True)
gc.collect()
print("Step 2 GC OK!", flush=True)

print("Step 5: _parse_variable_declarations on c34 ...", flush=True)
res2 = ParsedTypeScriptFile(file_path=str(p), language="typescript")
ast_parser._parse_variable_declarations(c34, content, res2, str(p), False)
print(f"Step 5 parsed {len(res2.symbols)} symbols", flush=True)
gc.collect()
print("Step 5 GC OK!", flush=True)
