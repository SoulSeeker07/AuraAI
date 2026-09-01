import gc
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser, ParsedTypeScriptFile

p = Path(".aura_staging/zustand_repo/src/middleware/devtools.ts")
content = p.read_bytes()
ast_parser = TypeScriptASTParser()
parser, _ = ast_parser._get_parser_and_lang(p)

for max_k in range(1, 36):
    parser.reset()
    tree = parser.parse(content)
    root = tree.root_node
    res = ParsedTypeScriptFile(file_path=str(p), language="typescript")
    
    for idx in range(min(max_k, root.named_child_count)):
        c = root.named_child(idx)
        ast_parser._visit_node(c, content, res, str(p), False)
        
    del tree
    del root
    gc.collect()
    print(f"Passed k={max_k} ({len(res.symbols)} symbols), GC OK!", flush=True)

print("\nALL 35 CHILDREN TESTED SUCCESSFULLY!")
