"""
Knowledge Intelligence Models

Data models for RAG 2.0 knowledge management.
"""

from dataclasses import dataclass, field, asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class KnowledgeType(str, Enum):
    """Types of knowledge."""
    PERSONAL = "personal"
    PROJECT = "project"
    CODE = "code"
    DOCUMENTATION = "documentation"
    CONVERSATION = "conversation"
    WORKSPACE = "workspace"


class ChunkType(str, Enum):
    """Types of document chunks."""
    SECTION = "section"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    FUNCTION = "function"
    CLASS = "class"
    CODE_BLOCK = "code_block"
    PAGE = "page"
    TABLE = "table"
    IMAGE = "image"
    ROW = "row"


class SourceType(str, Enum):
    """Source file types."""
    PDF = "pdf"
    MARKDOWN = "markdown"
    WORD = "docx"
    POWERPOINT = "pptx"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    C_SHARP = "csharp"
    YAML = "yaml"
    XML = "xml"
    TOML = "toml"
    TXT = "txt"
    LOGS = "logs"
    IMAGE = "image"
    AUDIO = "audio"
    MARKDOWN_ALL = "markdown_all"


class MetadataType(str, Enum):
    """Metadata types."""
    SOURCE = "source"
    PROJECT = "project"
    AUTHOR = "author"
    LANGUAGE = "language"
    TAGS = "tags"
    CREATED = "created"
    MODIFIED = "modified"
    CHUNK_TYPE = "chunk_type"
    FILE_TYPE = "file_type"
    IMPORTANCE = "importance"
    LANGUAGE_FAMILY = "language_family"


class EmbeddingProvider(str, Enum):
    """Embedding provider options."""
    OPENAI = "openai"
    GEMINI = "gemini"
    LOCAL = "local"
    HUGGINGFACE = "huggingface"


class RetrievalStrategy(str, Enum):
    """Retrieval strategies."""
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    KEYWORD = "keyword"
    GRAPH = "graph"


class RetrievalMode(str, Enum):
    """Retrieval modes for the RAG system."""
    SEMANTIC = "semantic"      # Pure semantic search
    HYBRID = "hybrid"          # Combined semantic + keyword
    KEYWORD = "keyword"        # Pure keyword search
    GRAPH = "graph"            # Knowledge graph traversal
    METADATA = "metadata"      # Filter by metadata


class CitationStyle(str, Enum):
    """Citation styles."""
    SIMPLE = "simple"
    DETAILED = "detailed"
    APA = "apa"


class IndexingStatus(str, Enum):
    """Indexing task status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# NOTE: The classes below (DocumentChunk, Citation, KnowledgeNode,
# KnowledgeEdge, IndexingTask, KnowledgeStats) each previously appeared TWICE
# in this module with conflicting field names. Python silently kept only the
# second definition of each, which would break any code written against the
# first. This version keeps a single definition per class (the richer one,
# with a working to_dict()). Double-check any existing callers still match
# these field names — see chat notes for exactly what changed.
# ---------------------------------------------------------------------------


@dataclass
class DocumentMetadata:
    """
    Metadata information for a document.
    """

    source_type: Optional[SourceType] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    author: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[List[str]] = None
    project: Optional[str] = None
    import_level: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_type: Optional[str] = None
    chunk_id: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    column_count: Optional[int] = None
    row_count: Optional[int] = None
    data_size: Optional[int] = None
    column_names: Optional[List[str]] = None
    source: Optional[str] = None

    def __init__(self, **kwargs):
        """
        Initialize DocumentMetadata with standard fields and parser-specific fields.
        Parser-specific fields are stored in extra_metadata dict.
        """
        # Store parser-specific fields in extra_metadata dict
        extra_metadata = {}
        for key in ['docstring', 'key_name', 'error_message', 'key_count', 'row_number', 'item_index',
                    'value', 'value_type', 'value_structure', 'chunk_index', 'total_chunks',
                    'source_id', 'line_start', 'line_end', 'column_count', 'row_count', 'data_size',
                    'column_names', 'chunk_id', 'item_index', 'file_path', 'file_name']:
            if key in kwargs:
                extra_metadata[key] = kwargs.pop(key)

        # Initialize with remaining kwargs
        self.source_type = kwargs.pop('source_type', None)
        self.file_path = kwargs.pop('file_path', None)
        self.file_name = kwargs.pop('file_name', None)
        self.file_type = kwargs.pop('file_type', None)
        self.file_size = kwargs.pop('file_size', None)
        self.created_at = kwargs.pop('created_at', None)
        self.modified_at = kwargs.pop('modified_at', None)
        self.page_count = kwargs.pop('page_count', None)
        self.chunk_count = kwargs.pop('chunk_count', None)
        self.author = kwargs.pop('author', None)
        self.title = kwargs.pop('title', None)
        self.description = kwargs.pop('description', None)
        self.language = kwargs.pop('language', None)
        self.tags = kwargs.pop('tags', [])
        self.project = kwargs.pop('project', None)
        self.import_level = kwargs.pop('import_level', None)
        self.extra_metadata = kwargs.pop('extra_metadata', {})
        self.chunk_type = kwargs.pop('chunk_type', None)
        self.chunk_id = kwargs.pop('chunk_id', None)
        self.line_start = kwargs.pop('line_start', None)
        self.line_end = kwargs.pop('line_end', None)
        self.column_count = kwargs.pop('column_count', None)
        self.row_count = kwargs.pop('row_count', None)
        self.data_size = kwargs.pop('data_size', None)
        self.column_names = kwargs.pop('column_names', None)
        self.source = kwargs.pop('source', None)

        # Store extra fields in extra_metadata dict
        self.extra_metadata = {**self.extra_metadata, **extra_metadata}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'source_type': self.source_type.value if self.source_type else None,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'page_count': self.page_count,
            'chunk_count': self.chunk_count,
            'author': self.author,
            'title': self.title,
            'description': self.description,
            'language': self.language,
            'tags': self.tags,
            'project': self.project,
            'import_level': self.import_level,
            'chunk_type': self.chunk_type,
            'chunk_id': self.chunk_id,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'column_count': self.column_count,
            'row_count': self.row_count,
            'data_size': self.data_size,
            'column_names': self.column_names,
            'source': self.source,
            'extra_metadata': self.extra_metadata,
        }


@dataclass
class DocumentChunk:
    """
    Represents a chunk of a document.
    """

    id: str
    content: str
    chunk_type: ChunkType
    source_type: SourceType
    source_file: str
    project: Optional[str] = None
    language: Optional[str] = None
    language_family: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    importance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, **kwargs):
        """
        Initialize DocumentChunk with required fields and additional metadata.
        Accepts both standard fields and parser-specific fields stored in metadata.
        """
        # Store parser-specific fields in metadata dict
        extra_metadata = {}
        for key in ['chunk_index', 'total_chunks', 'source_id', 'line_start', 'line_end', 'column_count', 'row_count', 'data_size', 'column_names', 'chunk_id']:
            if key in kwargs:
                extra_metadata[key] = kwargs.pop(key)

        # Initialize with remaining kwargs
        object.__setattr__(self, 'id', kwargs.pop('id'))
        object.__setattr__(self, 'content', kwargs.pop('content'))
        object.__setattr__(self, 'chunk_type', kwargs.pop('chunk_type'))
        object.__setattr__(self, 'source_type', kwargs.pop('source_type'))
        object.__setattr__(self, 'source_file', kwargs.pop('source_file'))
        object.__setattr__(self, 'project', kwargs.pop('project', None))
        object.__setattr__(self, 'language', kwargs.pop('language', None))
        object.__setattr__(self, 'language_family', kwargs.pop('language_family', None))
        object.__setattr__(self, 'tags', kwargs.pop('tags', []))
        object.__setattr__(self, 'created_at', kwargs.pop('created_at', datetime.now()))
        object.__setattr__(self, 'modified_at', kwargs.pop('modified_at', datetime.now()))
        object.__setattr__(self, 'page_number', kwargs.pop('page_number', None))
        object.__setattr__(self, 'line_number', kwargs.pop('line_number', None))
        object.__setattr__(self, 'importance', kwargs.pop('importance', 0.5))

        # `metadata` may arrive as a DocumentMetadata dataclass instance (most
        # parsers do this), a plain dict, or be omitted entirely. Normalize it
        # to a plain dict so downstream `{**self.metadata, ...}` merging works.
        raw_metadata = kwargs.pop('metadata', {})
        if is_dataclass(raw_metadata) and not isinstance(raw_metadata, type):
            raw_metadata = asdict(raw_metadata)
        elif not isinstance(raw_metadata, dict):
            raw_metadata = {}
        object.__setattr__(self, 'metadata', raw_metadata)

        # Store extra fields in metadata dict
        self.metadata = {**self.metadata, **extra_metadata}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'content': self.content,
            'chunk_type': self.chunk_type.value,
            'source_type': self.source_type.value,
            'source_file': self.source_file,
            'project': self.project,
            'language': self.language,
            'language_family': self.language_family,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'page_number': self.page_number,
            'line_number': self.line_number,
            'importance': self.importance,
            'metadata': self.metadata,
        }


@dataclass
class Citation:
    """Citation information for a document chunk."""
    id: str
    chunk_id: str
    source_file: str
    source_type: SourceType
    page: Optional[int] = None
    line: Optional[int] = None
    title: Optional[str] = None
    text: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'chunk_id': self.chunk_id,
            'source_file': self.source_file,
            'source_type': self.source_type.value,
            'page': self.page,
            'line': self.line,
            'title': self.title,
            'text': self.text,
            'score': self.score,
        }


@dataclass
class KnowledgeNode:
    """
    Represents a node in the knowledge graph.
    """

    id: str
    type: str
    name: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'description': self.description,
            'properties': self.properties,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class KnowledgeEdge:
    """
    Represents an edge (relationship) in the knowledge graph.
    """

    id: str
    source: str
    target: str
    relation: str
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'source': self.source,
            'target': self.target,
            'relation': self.relation,
            'weight': self.weight,
            'properties': self.properties,
        }


@dataclass
class IndexingTask:
    """
    Represents an indexing task.
    """

    id: str
    file_path: str
    file_type: SourceType
    status: str = "pending"
    progress: float = 0.0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    chunks_created: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'file_path': self.file_path,
            'file_type': self.file_type.value,
            'status': self.status,
            'progress': self.progress,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'chunks_created': self.chunks_created,
        }


@dataclass
class KnowledgeStats:
    """
    Knowledge store statistics.
    """

    total_chunks: int = 0
    total_documents: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    by_source_type: Dict[str, int] = field(default_factory=dict)
    by_project: Dict[str, int] = field(default_factory=dict)
    by_chunk_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_chunks': self.total_chunks,
            'total_documents': self.total_documents,
            'total_nodes': self.total_nodes,
            'total_edges': self.total_edges,
            'by_source_type': self.by_source_type,
            'by_project': self.by_project,
            'by_chunk_type': self.by_chunk_type,
        }


@dataclass
class RetrievalResult:
    """Result of a knowledge retrieval operation."""
    chunks: List[DocumentChunk]
    citations: Optional[List[Citation]] = None
    context: Optional[str] = None
    mode: str = "semantic"
    query: str = ""
    retrieved_at: datetime = field(default_factory=datetime.now)
    total_retrieved: int = 0
    confidence: float = 0.0


@dataclass
class KnowledgeContext:
    """
    Represents structured knowledge context for LLM.
    """

    question: str
    chunks: List[DocumentChunk] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    knowledge_graph: List[KnowledgeNode] = field(default_factory=list)
    knowledge_graph_edges: List[KnowledgeEdge] = field(default_factory=list)
    confidence: float = 1.0
    related_documents: List[str] = field(default_factory=list)
    project_context: Optional[str] = None
    summary: str = ""
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'question': self.question,
            'chunks': [chunk.to_dict() for chunk in self.chunks],
            'citations': [citation.to_dict() for citation in self.citations],
            'knowledge_graph': [
                node.to_dict() for node in self.knowledge_graph
            ],
            'knowledge_graph_edges': [
                edge.to_dict() for edge in self.knowledge_graph_edges
            ],
            'confidence': self.confidence,
            'related_documents': self.related_documents,
            'project_context': self.project_context,
            'summary': self.summary,
            'sources': self.sources,
        }

    def get_context_text(self, max_chunks: int = 10) -> str:
        """
        Get context text for LLM.

        Args:
            max_chunks: Maximum chunks to include

        Returns:
            Formatted context text
        """
        if not self.chunks:
            return ""

        context_parts = []
        context_parts.append(f"## Question: {self.question}\n")

        for i, chunk in enumerate(self.chunks[:max_chunks]):
            context_parts.append(f"### Source {i + 1}: {chunk.source_file}")

            if chunk.project:
                context_parts.append(f"Project: {chunk.project}")

            if chunk.page_number:
                context_parts.append(f"Page: {chunk.page_number}")

            context_parts.append(f"Content: {chunk.content}\n")

        context_parts.append(f"\n---\nSummary: {self.summary}")
        return "\n".join(context_parts)