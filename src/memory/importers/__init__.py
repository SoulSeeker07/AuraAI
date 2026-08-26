"""
External Memory Importers Package
Location: src/memory/importers/

Provides adapters for importing memory from external AI assistants
(Claude, ChatGPT) into AuraAI's CognitiveMemoryEngine.
"""

from .base_importer import ExternalMemoryImporter, ImportResult, RawMemoryFact
from .schema_mapper import SchemaMapper

__all__ = [
    "ExternalMemoryImporter",
    "ImportResult",
    "RawMemoryFact",
    "SchemaMapper",
]
