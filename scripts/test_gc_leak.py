import gc
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser

ast_parser = TypeScriptASTParser()
repo = Path(".aura_staging/zustand_repo").resolve()
p_devtools = repo / "src" / "middleware" / "devtools.ts"
p_immer = repo / "src" / "middleware" / "immer.ts"

content1 = p_devtools.read_bytes()
content2 = p_immer.read_bytes()

p, _ = ast_parser._get_parser_and_lang(p_devtools)
t1 = p.parse(content1)
t2 = p.parse(content2)

from engineering.language_providers.typescript.parser import ParsedTypeScriptFile

res1 = ParsedTypeScriptFile(file_path=str(p_devtools), language="typescript")
for idx in range(t1.root_node.child_count):
    child = t1.root_node.child(idx)
    if child:
        print(f"Visiting child [{idx}]: {child.type} ...", flush=True)
        ast_parser._visit_node(child, content1, res1, str(p_devtools), False)
        print(f"  Done child [{idx}]: {len(res1.symbols)} symbols. Running gc.collect()...", flush=True)
        gc.collect()
        print(f"  gc.collect() OK after child [{idx}]", flush=True)

print("All devtools children OK!")

res2 = ParsedTypeScriptFile(file_path=str(p_immer), language="typescript")
for idx in range(t2.root_node.child_count):
    child = t2.root_node.child(idx)
    if child:
        ast_parser._visit_node(child, content2, res2, str(p_immer), False)

print(f"res2 parsed {len(res2.symbols)} symbols. Running gc.collect()...")
gc.collect()
print("After res2 gc.collect() SUCCESS!")
