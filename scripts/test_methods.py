import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from engineering.language_providers.typescript.parser import TypeScriptASTParser, ParsedTypeScriptFile
import tree_sitter_typescript as tst
from tree_sitter import Language, Parser

ts_lang = Language(tst.language_typescript())
parser = Parser(ts_lang)
ast_parser = TypeScriptASTParser()

repo = Path(".aura_staging/zustand_repo").resolve()
files = [p for p in sorted(repo.rglob("*")) if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")]

for method_name in ["imports", "type_alias", "interface", "functions", "variables", "body"]:
    print(f"\n--- TESTING METHOD: {method_name} ---", flush=True)
    for idx in range(20, 36):
        p = files[idx]
        content = p.read_bytes()
        tree = parser.parse(content)
        res = ParsedTypeScriptFile(file_path=str(p), language="typescript")
        root = tree.root_node
        for c_idx in range(root.child_count):
            child = root.child(c_idx)
            if not child: continue
            if method_name == "imports" and child.type == "import_statement":
                ast_parser._parse_import_statement(child, content, res)
            elif method_name == "type_alias" and child.type == "type_alias_declaration":
                ast_parser._parse_type_alias_declaration(child, content, res, str(p), False)
            elif method_name == "interface" and child.type == "interface_declaration":
                ast_parser._parse_interface_declaration(child, content, res, str(p), False)
            elif method_name == "functions" and child.type == "function_declaration":
                ast_parser._parse_function_declaration(child, content, res, str(p), False)
            elif method_name == "variables" and child.type in ("lexical_declaration", "variable_declaration"):
                ast_parser._parse_variable_declarations(child, content, res, str(p), False)
            elif method_name == "body":
                ast_parser._analyze_body(child, content)
        print(f"[{idx}] {p.name} -> {len(res.symbols)} symbols", flush=True)
        del root
        del tree
    print(f"METHOD {method_name} PASSED!")
