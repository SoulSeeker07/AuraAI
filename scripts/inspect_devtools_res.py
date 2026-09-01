import gc
import sys
from pathlib import Path
import tree_sitter_typescript as tst
from tree_sitter import Language, Parser

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser, HookInfo

ast_parser = TypeScriptASTParser()

def queue_analyze_body(root, source, lang="typescript"):
    hooks = []
    calls = set()
    jsx_elements = set()
    has_jsx = False

    queue = [root]
    while queue:
        curr = queue.pop(0)
        node_type = curr.type

        if node_type == "call_expression":
            fn_node = curr.child_by_field_name("function")
            if fn_node:
                fn_name = ast_parser._get_node_text(fn_node, source)
                if len(fn_name) <= 80 and "\n" not in fn_name:
                    calls.add(fn_name)

                if fn_name.startswith("use") or ".use" in fn_name:
                    line_no = curr.start_point.row + 1
                    hook_deps = ast_parser._extract_hook_dependency_array(curr, source)
                    hooks.append(HookInfo(
                        name=fn_name,
                        line=line_no,
                        dependencies=hook_deps,
                    ))

        elif node_type in ("jsx_opening_element", "jsx_self_closing_element"):
            has_jsx = True
            name_node = curr.child_by_field_name("name")
            if name_node:
                elem_name = ast_parser._get_node_text(name_node, source)
                if elem_name and elem_name[0].isupper():
                    jsx_elements.add(elem_name)
                    calls.add(elem_name)
        elif node_type in ("jsx_element", "jsx_fragment"):
            has_jsx = True

        for idx in range(curr.named_child_count):
            ch = curr.named_child(idx)
            if ch:
                queue.append(ch)

    return hooks, sorted(list(calls)), sorted(list(jsx_elements)), has_jsx

ast_parser._analyze_body = queue_analyze_body

p = Path(".aura_staging/zustand_repo/src/middleware/devtools.ts").resolve()
content = p.read_bytes()

res = ast_parser.parse_source(content, p)
print(f"Parsed devtools.ts: {len(res.symbols)} symbols, {len(res.call_edges)} call edges")

print("Running gc.collect() ...")
gc.collect()
print("GC SUCCESS!")

repo = Path(".aura_staging/zustand_repo").resolve()
files = [f for f in sorted(repo.rglob("*")) if f.is_file() and f.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")]

print(f"\nScanning ALL {len(files)} files in Zustand with queue_analyze_body...")
total_syms = 0
for idx, f in enumerate(files, 1):
    res = ast_parser.parse_source(f.read_bytes(), f)
    total_syms += len(res.symbols)
    print(f"[{idx}/{len(files)}] {f.name} -> {len(res.symbols)} symbols", flush=True)

print(f"\n🎉 100% COMPLETE! All {len(files)} files in Zustand parsed with 0 errors! Total symbols: {total_syms}")
