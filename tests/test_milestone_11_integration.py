"""
Milestone 11 Integration Tests

Tests the complete Knowledge Intelligence (RAG 2.0) system end-to-end.
"""

import pytest
import tempfile
import os
from pathlib import Path
import json
import yaml
import csv

from src.knowledge.knowledge_manager import KnowledgeManager
from src.knowledge.models import RetrievalMode, SourceType, ChunkType
from src.knowledge.parsers import get_parser_registry


class TestKnowledgeManagerIntegration:
    """Test the complete Knowledge Manager integration."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.manager = KnowledgeManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove test directory
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_parser_registry_availability(self):
        """Test that all parsers are registered."""
        registry = get_parser_registry()
        parsers = registry.list_parsers()

        expected_parsers = [
            'pdf', 'markdown', 'python', 'docx', 'pptx',
            'html', 'json', 'yaml', 'csv', 'log'
        ]

        assert len(parsers) > 0, "No parsers registered"
        for parser_name in expected_parsers:
            assert parser_name in parsers, f"Parser '{parser_name}' not found"

    def test_markdown_parsing(self):
        """Test Markdown document parsing."""
        # Create a test Markdown file
        md_file = os.path.join(self.test_dir, "test.md")
        content = """# Test Document

This is a test document.

## Section 1

Some content here.

## Section 2

More content here.
"""

        with open(md_file, 'w') as f:
            f.write(content)

        # Parse the file
        from pathlib import Path
        parser_class = get_parser_registry().get_parser(Path(md_file))
        assert parser_class is not None, "Could not get parser for Markdown file"

        parser = parser_class()
        chunks = parser.parse(Path(md_file))
        assert len(chunks) > 0, "No chunks created"
        assert chunks[0].chunk_type == ChunkType.SECTION, "Expected section chunks"

    def test_python_code_parsing(self):
        """Test Python code parsing with function-level chunking."""
        py_file = os.path.join(self.test_dir, "test.py")
        code = '''def greet(name):
    """Return a greeting."""
    return f"Hello, {name}!"

def add(a, b):
    """Add two numbers."""
    return a + b
'''

        with open(py_file, 'w') as f:
            f.write(code)

        parser_class = get_parser_registry().get_parser(Path(py_file))
        assert parser_class is not None, "Could not get parser for Python file"

        parser = parser_class()
        chunks = parser.parse(Path(py_file))
        assert len(chunks) > 0, "No chunks created"

        # Check that we got function chunks
        function_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]
        assert len(function_chunks) >= 2, f"Expected at least 2 function chunks, got {len(function_chunks)}"

    def test_json_parsing(self):
        """Test JSON file parsing."""
        json_file = os.path.join(self.test_dir, "test.json")
        data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ],
            "settings": {
                "theme": "dark",
                "language": "en"
            }
        }

        with open(json_file, 'w') as f:
            json.dump(data, f)

        parser_class = get_parser_registry().get_parser(Path(json_file))
        assert parser_class is not None, "Could not get parser for JSON file"

        parser = parser_class()
        chunks = parser.parse(Path(json_file))
        assert len(chunks) > 0, "No chunks created"

    def test_yaml_parsing(self):
        """Test YAML file parsing."""
        yaml_file = os.path.join(self.test_dir, "test.yaml")
        data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "mydb"
            },
            "logging": {
                "level": "DEBUG",
                "format": "json"
            }
        }

        with open(yaml_file, 'w') as f:
            yaml.dump(data, f)

        parser_class = get_parser_registry().get_parser(Path(yaml_file))
        assert parser_class is not None, "Could not get parser for YAML file"

        parser = parser_class()
        chunks = parser.parse(Path(yaml_file))
        assert len(chunks) > 0, "No chunks created"

    def test_csv_parsing(self):
        """Test CSV file parsing."""
        csv_file = os.path.join(self.test_dir, "test.csv")
        content = """name,age,country
Alice,30,USA
Bob,25,Canada
Charlie,35,UK
"""

        with open(csv_file, 'w') as f:
            f.write(content)

        parser_class = get_parser_registry().get_parser(Path(csv_file))
        assert parser_class is not None, "Could not get parser for CSV file"

        parser = parser_class()
        chunks = parser.parse(Path(csv_file))
        assert len(chunks) > 0, "No chunks created"
        assert chunks[0].chunk_type == ChunkType.ROW, "Expected row chunks"

    def test_indexer_initialization(self):
        """Test indexer can be initialized."""
        # This is a basic check that the indexer exists and can be instantiated
        from src.knowledge.indexer import Indexer
        from src.knowledge.embedding_manager import EmbeddingManager
        from src.knowledge.vector_store import VectorStore
        from src.knowledge.graph_store import GraphStore
        from src.knowledge.citation_engine import CitationEngine

        # Note: We can't fully test indexing without actual files and embeddings
        # This just verifies the classes can be instantiated
        embedding_manager = EmbeddingManager()
        vector_store = VectorStore(store_path=self.test_dir)
        graph_store = GraphStore(vector_store)
        citation_engine = CitationEngine()
        indexer = Indexer(vector_store, graph_store, embedding_manager, citation_engine)

        assert indexer is not None, "Indexer initialization failed"

    def test_file_watcher_initialization(self):
        """Test file watcher can be initialized."""
        from src.knowledge.file_watcher import KnowledgeFileWatcher

        from src.knowledge.indexer import Indexer
        from src.knowledge.embedding_manager import EmbeddingManager
        from src.knowledge.vector_store import VectorStore
        from src.knowledge.graph_store import GraphStore
        from src.knowledge.citation_engine import CitationEngine

        embedding_manager = EmbeddingManager()
        vector_store = VectorStore(store_path=self.test_dir)
        graph_store = GraphStore(vector_store)
        citation_engine = CitationEngine()
        indexer = Indexer(vector_store, graph_store, embedding_manager, citation_engine)

        # Initialize file watcher (won't actually watch unless directories are set)
        watcher = KnowledgeFileWatcher(indexer, [self.test_dir])

        assert watcher is not None, "File watcher initialization failed"

    def test_retrieval_engine_initialization(self):
        """Test retrieval engine can be initialized."""
        from src.knowledge.retrieval_engine import RetrievalEngine
        from src.knowledge.embedding_manager import EmbeddingManager
        from src.knowledge.vector_store import VectorStore
        from src.knowledge.graph_store import GraphStore
        from src.knowledge.chunker import Chunker

        embedding_manager = EmbeddingManager()
        vector_store = VectorStore(store_path=self.test_dir)
        graph_store = GraphStore(vector_store)
        chunker = Chunker()

        retrieval_engine = RetrievalEngine(vector_store, graph_store, chunker)

        assert retrieval_engine is not None, "Retrieval engine initialization failed"

    def test_all_parsers_supported_extensions(self):
        """Test all parsers have correct supported extensions."""
        registry = get_parser_registry()

        parsers = registry.list_parsers()

        expected_extensions = {
            'pdf': ['.pdf'],
            'markdown': ['.md', '.markdown', '.mkd'],
            'python': ['.py', '.pyi'],
            'docx': ['.docx'],
            'pptx': ['.pptx'],
            'html': ['.html', '.htm'],
            'json': ['.json'],
            'yaml': ['.yaml', '.yml'],
            'csv': ['.csv'],
            'log': ['.log']
        }

        for parser_name in parsers:
            # Get the parser class
            parser_class = registry._name_map.get(parser_name)
            if parser_class:
                instance = parser_class()
                extensions = getattr(instance, 'supported_extensions', set())

                expected = expected_extensions.get(parser_name.lower(), set())
                assert extensions == expected, f"Parser '{parser_name}' has incorrect extensions"

    def test_models_completeness(self):
        """Test that all required models exist and have correct structure."""
        from src.knowledge.models import (
            DocumentChunk, KnowledgeNode, KnowledgeEdge, Citation,
            KnowledgeContext, RetrievalResult, IndexingTask,
            KnowledgeStats, RetrievalMode, SourceType, ChunkType,
            EmbeddingProvider, KnowledgeType
        )

        # Test DocumentChunk
        chunk = DocumentChunk(
            id="test_1",
            content="Test content",
            chunk_type=ChunkType.PARAGRAPH,
            source_type=SourceType.MARKDOWN,
            source_file="test.md"
        )
        assert chunk.id == "test_1"
        assert chunk.content == "Test content"
        assert chunk.to_dict() is not None

        # Test KnowledgeNode
        node = KnowledgeNode(
            id="node_1",
            type="test_type",
            name="Test Node"
        )
        assert node.id == "node_1"
        assert node.to_dict() is not None

        # Test RetrievalMode enum
        assert RetrievalMode.SEMANTIC is not None
        assert RetrievalMode.HYBRID is not None
        assert RetrievalMode.KEYWORD is not None

        # Test SourceType enum
        assert SourceType.PYTHON is not None
        assert SourceType.MARKDOWN is not None

    def test_embedding_provider_interface(self):
        """Test embedding provider base class."""
        from src.knowledge.embedding_manager import BaseEmbeddingProvider

        # Base class should be abstract
        assert hasattr(BaseEmbeddingProvider, 'get_embedding')
        assert hasattr(BaseEmbeddingProvider, 'get_embeddings')

    def test_dataclass_serialization(self):
        """Test that all dataclasses can be serialized."""
        from src.knowledge.models import (
            DocumentChunk, Citation, KnowledgeNode, KnowledgeEdge,
            IndexingTask, KnowledgeStats
        )

        # Test DocumentChunk
        chunk = DocumentChunk(
            id="test_1",
            content="Test",
            chunk_type=ChunkType.SECTION,
            source_type=SourceType.PYTHON,
            source_file="test.py"
        )
        assert chunk.to_dict() is not None
        assert 'id' in chunk.to_dict()

        # Test Citation
        citation = Citation(
            id="cite_1",
            chunk_id="chunk_1",
            source_file="test.md",
            source_type=SourceType.MARKDOWN,
            score=0.95
        )
        assert citation.to_dict() is not None

        # Test KnowledgeNode
        node = KnowledgeNode(
            id="node_1",
            type="test",
            name="Test",
            description="A test node"
        )
        assert node.to_dict() is not None

        # Test IndexingTask
        task = IndexingTask(
            id="task_1",
            file_path="test.py",
            file_type=SourceType.PYTHON
        )
        assert task.to_dict() is not None

    def test_metadata_extraction(self):
        """Test metadata extraction for different file types."""
        from src.knowledge.metadata_manager import MetadataManager
        from src.knowledge.models import SourceType

        manager = MetadataManager()

        # Test Python file metadata
        python_content = '''def test():
    """A test function."""
    pass
'''
        metadata = manager.extract_metadata("test.py", SourceType.PYTHON, python_content)
        assert SourceType.PYTHON.value in metadata.get('file_type', '')
        assert 'created' in metadata
        assert 'modified' in metadata

    def test_enums_have_proper_values(self):
        """Test that all enums have valid values."""
        from src.knowledge.models import (
            RetrievalMode, SourceType, ChunkType,
            EmbeddingProvider, CitationStyle, KnowledgeType
        )

        # Test RetrievalMode
        assert len(RetrievalMode) > 0
        assert RetrievalMode.SEMANTIC in [m.value for m in RetrievalMode]
        assert RetrievalMode.HYBRID in [m.value for m in RetrievalMode]

        # Test SourceType
        assert len(SourceType) > 0
        assert SourceType.PYTHON in [s.value for s in SourceType]

        # Test ChunkType
        assert len(ChunkType) > 0
        assert ChunkType.FUNCTION in [c.value for c in ChunkType]

        # Test EmbeddingProvider
        assert len(EmbeddingProvider) > 0

        # Test KnowledgeType
        assert len(KnowledgeType) > 0


class TestKnowledgeManagerSmokeTests:
    """Smoke tests for Knowledge Manager to verify basic functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = KnowledgeManager()

    def test_manager_initialization(self):
        """Test Knowledge Manager initializes correctly."""
        assert self.manager is not None
        assert hasattr(self.manager, 'knowledge_db')
        assert hasattr(self.manager, 'vector_store')
        assert hasattr(self.manager, 'retrieval_engine')
        assert hasattr(self.manager, 'indexer')

    def test_cache_manager_access(self):
        """Test cache manager is accessible."""
        assert self.manager.cache_manager is not None

    def test_freshness_checker_access(self):
        """Test freshness checker is accessible."""
        assert self.manager.freshness_checker is not None

    def test_learning_engine_access(self):
        """Test learning engine is accessible."""
        assert self.manager.learning_engine is not None

    def test_topic_memory_access(self):
        """Test topic memory is accessible."""
        assert self.manager.topic_memory is not None

    def test_knowledge_graph_access(self):
        """Test knowledge graph is accessible."""
        assert self.manager.knowledge_graph is not None

    def test_statistics_tracking(self):
        """Test statistics are tracked."""
        assert hasattr(self.manager, '_total_retrievals')
        assert hasattr(self.manager, '_total_learnings')
        assert self.manager._total_retrievals >= 0
        assert self.manager._total_learnings >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
