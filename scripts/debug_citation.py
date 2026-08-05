import sys

sys.path.insert(0, "src")
import inspect

from research.citation_builder import Citation, CitationBuilder

print("citation_builder.py location:", inspect.getfile(CitationBuilder))
print("Citation fields:", list(Citation.__dataclass_fields__.keys()))
print()
print(inspect.getsource(CitationBuilder.build_citations))
