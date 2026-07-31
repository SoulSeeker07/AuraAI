"""
Knowledge Brain - Aura's self-learning knowledge system.

Milestone 3: Make Aura self-learning and separate from normal chatbot.

Key Features:
    1. Knows what it knows (explicit knowledge base)
    2. Knows what it doesn't know (auto-discovers knowledge gaps)
    3. Knows when knowledge is fresh (lifecycle management)
    4. Knows how knowledge is connected (knowledge graph)
    5. Knows how to learn (automatic knowledge acquisition)

Architecture:
    KnowledgeManager (Orchestrator)
        ↓
    ┌──────────────────────────────────────────────┐
    │  Knowledge Components                         │
    ├──────────────────────────────────────────────┤
    │  KnowledgeDB - Store factual knowledge        │
    │  TopicMemory - Organize by topic              │
    │  FreshnessChecker - Manage knowledge lifecycle│
    │  KnowledgeGraph - Build relationships         │
    │  LearningEngine - Auto-update knowledge       │
    │  CacheManager - Cache search results          │
    └──────────────────────────────────────────────┘

Usage:
    from knowledge.knowledge_manager import KnowledgeManager

    manager = KnowledgeManager()

    # Retrieve facts
    result = manager.retrieve_facts("Python version")
    if result.needs_refresh:
        # Perform search and learn
        results = manager.search_web("Python version")
        manager.learn_from_search_results(results, "Python version")

    # Get related topics
    related = manager.get_related_topics("Python")

    # Refresh expired knowledge
    manager.refresh_expired_knowledge()
"""

# ==================== OLD KNOWLEDGE SYSTEM (Backward Compatibility) ====================
from .knowledge_db import KnowledgeDB, KnowledgeFact
from .topic_memory import TopicMemory, TopicNode
from .freshness_checker import FreshnessChecker, KnowledgeCategory
from .knowledge_graph import KnowledgeGraph, KnowledgeNode
from .learning_engine import LearningEngine, LearnedFact
from .cache_manager import CacheManager, CachedSearchResult

# ==================== NEW RAG 2.0 SYSTEM ====================
from .models import (
    DocumentChunk, KnowledgeNode as RAGKnowledgeNode,
    KnowledgeEdge, Citation, KnowledgeContext, RetrievalResult,
    IndexingTask, KnowledgeStats, RetrievalMode
)
from .metadata_manager import MetadataManager
from .chunker import Chunker
from .embedding_manager import EmbeddingManager
from .vector_store import VectorStore
from .graph_store import GraphStore
from .retrieval_engine import RetrievalEngine
from .ranking_engine import RankingEngine
from .citation_engine import CitationEngine
from .knowledge_context import KnowledgeContext as ContextBuilder
from .indexer import Indexer
from .file_watcher import KnowledgeFileWatcher
from .knowledge_manager import KnowledgeManager, IndexingProgress

__version__ = "2.0.0"
__all__ = [
    # Old Knowledge System
    "KnowledgeDB",
    "KnowledgeFact",
    "TopicMemory",
    "TopicNode",
    "FreshnessChecker",
    "KnowledgeCategory",
    "KnowledgeGraph",
    "KnowledgeNode",
    "LearningEngine",
    "LearnedFact",
    "CacheManager",
    "CachedSearchResult",
    "KnowledgeManager",
    "KnowledgeRetrievalResult",
    # New RAG 2.0 System
    "DocumentChunk",
    "KnowledgeNode as RAGKnowledgeNode",
    "KnowledgeEdge",
    "Citation",
    "KnowledgeContext",
    "RetrievalResult",
    "IndexingTask",
    "KnowledgeStats",
    "RetrievalMode",
    "MetadataManager",
    "Chunker",
    "EmbeddingManager",
    "VectorStore",
    "GraphStore",
    "RetrievalEngine",
    "RankingEngine",
    "CitationEngine",
    "IndexingProgress",
    "KnowledgeFileWatcher",
]

__doc__ = """
Knowledge Brain - Aura's self-learning knowledge system

Milestone 3: Make Aura self-learning and separate from normal chatbot

Key Features:
    1. Knows what it knows (explicit knowledge base)
    2. Knows what it doesn't know (auto-discovers knowledge gaps)
    3. Knows when knowledge is fresh (lifecycle management)
    4. Knows how knowledge is connected (knowledge graph)
    5. Knows how to learn (automatic knowledge acquisition)

Architecture:
    KnowledgeManager (Orchestrator)
        ↓
    ┌──────────────────────────────────────────────┐
    │  Knowledge Components                         │
    ├──────────────────────────────────────────────┤
    │  KnowledgeDB - Store factual knowledge        │
    │  TopicMemory - Organize by topic              │
    │  FreshnessChecker - Manage knowledge lifecycle│
    │  KnowledgeGraph - Build relationships         │
    │  LearningEngine - Auto-update knowledge       │
    │  CacheManager - Cache search results          │
    └──────────────────────────────────────────────┘

Usage:
    from knowledge.knowledge_manager import KnowledgeManager

    manager = KnowledgeManager()

    # Retrieve facts
    result = manager.retrieve_facts("Python version")
    if result.needs_refresh:
        # Perform search and learn
        results = manager.search_web("Python version")
        manager.learn_from_search_results(results, "Python version")

    # Get related topics
    related = manager.get_related_topics("Python")

    # Refresh expired knowledge
    manager.refresh_expired_knowledge()
"""
