"""
Memory System

Provides intelligent memory management for Aura with:
- 5 memory layers (Working, Session, Long-Term, Knowledge, Workspace)
- Importance scoring
- Category classification
- Smart retrieval with ranking
- Forgetting engine
- Conflict resolution
- Sensitive data handling
"""

from .memory_types import (
    MemoryFact,
    MemoryLayer,
    CategoryType,
    ImportanceLevel,
    RiskLevel,
    MemoryAnalysisResult,
    MemoryRetrievalResult,
    ForgettingResult,
    ConflictResult,
    MemorySummary,
    MemoryStore,
)

from .memory_analyzer import MemoryAnalyzer

from .memory_manager_v2 import MemoryManagerV2

__all__ = [
    # Types
    'MemoryFact',
    'MemoryLayer',
    'CategoryType',
    'ImportanceLevel',
    'RiskLevel',
    'MemoryAnalysisResult',
    'MemoryRetrievalResult',
    'ForgettingResult',
    'ConflictResult',
    'MemorySummary',
    'MemoryStore',
    
    # Components
    'MemoryAnalyzer',
    'MemoryManagerV2',
]
