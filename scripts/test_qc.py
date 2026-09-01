import sys
from pathlib import Path
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_typescript as tst

ts_lang = Language(tst.language_typescript())
tsx_lang = Language(tst.language_tsx())

query_str = """
(call_expression function: (_) @fn) @call
(jsx_opening_element name: (_) @jsx_tag)
(jsx_self_closing_element name: (_) @jsx_tag)
(jsx_element) @jsx_elem
"""

q = Query(tsx_lang, query_str)
qc = QueryCursor(q)

parser = Parser(tsx_lang)
code = b'''
function MyComponent() {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch('/api');
  }, [url]);
  return <div className="card"><CustomCard title="hello" /><></></div>;
}
'''
tree = parser.parse(code)
captures = qc.captures(tree.root_node)
print("Captures keys:", captures.keys())
for k, nodes in captures.items():
    print(f"Capture {k}: {len(nodes)} nodes")
    for n in nodes:
        print(f"  [{k}] {code[n.start_byte:n.end_byte].decode(errors='replace')}")
