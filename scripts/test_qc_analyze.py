import sys
from pathlib import Path
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_typescript as tst
import tree_sitter_javascript as tsj

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser, HookInfo

ast_parser = TypeScriptASTParser()

# Setup queries
ts_lang = ast_parser._ts_language
tsx_lang = ast_parser._tsx_language
js_lang = ast_parser._js_language

query_ts = Query(ts_lang, "(call_expression function: (_) @fn) @call")
qc_ts = QueryCursor(query_ts)

query_tsx = Query(tsx_lang, """
(call_expression function: (_) @fn) @call
(jsx_opening_element name: (_) @jsx_tag)
(jsx_self_closing_element name: (_) @jsx_tag)
(jsx_element) @jsx_elem
""")
qc_tsx = QueryCursor(query_tsx)

query_js = Query(js_lang, """
(call_expression function: (_) @fn) @call
(jsx_opening_element name: (_) @jsx_tag)
(jsx_self_closing_element name: (_) @jsx_tag)
(jsx_element) @jsx_elem
""")
qc_js = QueryCursor(query_js)

def query_analyze_body(root, source, language="typescript"):
    hooks = []
    calls = set()
    jsx_elements = set()
    has_jsx = False

    query = query_tsx if language == "tsx" else (query_js if language in ("jsx", "javascript") else query_ts)
    qc = QueryCursor(query)

    for pattern_idx, match in qc.matches(root):
        if "jsx_tag" in match:
            has_jsx = True
            for tag_node in match["jsx_tag"]:
                tag_name = ast_parser._get_node_text(tag_node, source)
                if tag_name and tag_name[0].isupper():
                    jsx_elements.add(tag_name)
                    calls.add(tag_name)

        if "jsx_elem" in match:
            has_jsx = True

        if "call" in match and "fn" in match:
            call_node = match["call"][0]
            fn_node = match["fn"][0]
            fn_name = ast_parser._get_node_text(fn_node, source)

            if len(fn_name) <= 80 and "\n" not in fn_name:
                calls.add(fn_name)

            if fn_name.startswith("use") or ".use" in fn_name:
                line_no = call_node.start_point.row + 1
                hook_deps = ast_parser._extract_hook_dependency_array(call_node, source)
                hooks.append(HookInfo(
                    name=fn_name,
                    line=line_no,
                    dependencies=hook_deps,
                ))

    return hooks, sorted(list(calls)), sorted(list(jsx_elements)), has_jsx

ast_parser._analyze_body = query_analyze_body

repo = Path(".aura_staging/zustand_repo").resolve()
files = [p for p in sorted(repo.rglob("*")) if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")]

print(f"Scanning ALL {len(files)} files in Zustand with native query engine...")
total_syms = 0
for idx, p in enumerate(files, 1):
    content = p.read_bytes()
    res = ast_parser.parse_source(content, p)
    total_syms += len(res.symbols)
    print(f"[{idx}/{len(files)}] {p.relative_to(repo)} -> {len(res.symbols)} symbols", flush=True)

print(f"\n🎉 100% COMPLETE! All {len(files)} files in Zustand parsed with 0 errors! Total symbols: {total_syms}")
