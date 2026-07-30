"""
Memory Manager

Manages memory operations for Aura.
Provides fact storage, retrieval, and context building.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class MemoryFact:
    """Represents a stored memory fact."""
    
    def __init__(
        self,
        category: str,
        key: str,
        value: str,
        timestamp: datetime = None,
        metadata: dict = None
    ):
        """
        Initialize a memory fact.
        
        Args:
            category: Category of the fact (e.g., "preferences", "project")
            key: Unique key for the fact
            value: Value of the fact
            timestamp: When the fact was created
            metadata: Additional metadata
        """
        self.category = category
        self.key = key
        self.value = value
        self.timestamp = timestamp or datetime.now()
        self.metadata = metadata or {}
    
    def __repr__(self) -> str:
        """String representation."""
        return f"MemoryFact({self.category}: {self.key}={self.value})"


class MemoryManager:
    """
    Manages memory operations.
    
    Responsibilities:
        - Store and retrieve memory facts
        - Build memory context
        - Extract facts from text
        - Manage fact expiration
        - Provide memory summaries
    """
    
    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize Memory Manager.
        
        Args:
            data_path: Path to store memory data
        """
        self.data_path = data_path or Path("Data/memory.json")
        self.facts: dict[str, list[MemoryFact]] = {}
        self._load_facts()
        
        logger.info(f"Memory Manager initialized")
    
    def remember(self, category: str, key: str, value: str) -> MemoryFact:
        """
        Store a memory fact.
        
        Args:
            category: Category of the fact
            key: Unique key
            value: Value to store
        
        Returns:
            The stored fact
        """
        fact = MemoryFact(category=category, key=key, value=value)
        
        if category not in self.facts:
            self.facts[category] = []
        
        # Remove existing fact with same key
        self.facts[category] = [
            f for f in self.facts[category] if f.key != key
        ]
        
        self.facts[category].append(fact)
        self._save_facts()
        
        logger.debug(f"Stored fact: {category}/{key}={value}")
        return fact
    
    def retrieve(self, category: str, key: str) -> Optional[MemoryFact]:
        """
        Retrieve a specific fact.
        
        Args:
            category: Category of the fact
            key: Key to retrieve
        
        Returns:
            Fact or None
        """
        if category not in self.facts:
            return None
        
        for fact in self.facts[category]:
            if fact.key == key:
                return fact
        
        return None
    
    def get_all_facts(self) -> list[MemoryFact]:
        """
        Get all facts.
        
        Returns:
            List of all facts
        """
        facts = []
        for category in self.facts:
            facts.extend(self.facts[category])
        return facts
    
    def get_facts_by_category(self, category: str) -> list[MemoryFact]:
        """
        Get facts by category.
        
        Args:
            category: Category to filter by
        
        Returns:
            List of facts in category
        """
        return self.facts.get(category, [])
    
    def get_context(self) -> str:
        """
        Build a memory context string.
        
        Returns:
            Formatted context string
        """
        if not self.facts:
            return "No memory facts stored yet."
        
        lines = []
        for category in sorted(self.facts.keys()):
            facts = sorted(set(f.value for f in self.facts[category]))
            if facts:
                lines.append(f"{category.title()}: {', '.join(facts)}")
        
        return "\n".join(lines)
    
    def get_recent_messages(self, limit: int = 10) -> list[dict]:
        """
        Get recent messages from chat log.
        
        Args:
            limit: Maximum number of messages
        
        Returns:
            List of recent messages
        """
        # This would typically load from a chat log file
        # For now, return empty list
        return []
    
    def get_all_categories(self) -> list[str]:
        """
        Get all memory categories.
        
        Returns:
            List of category names
        """
        return list(self.facts.keys())
    
    def _save_facts(self):
        """Save facts to disk."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'facts': [
                    {
                        'category': f.category,
                        'key': f.key,
                        'value': f.value,
                        'timestamp': f.timestamp.isoformat(),
                        'metadata': f.metadata
                    }
                    for f in self.get_all_facts()
                ]
            }
            
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to save facts: {e}")
    
    def _load_facts(self):
        """Load facts from disk."""
        try:
            if self.data_path.exists():
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for fact_data in data.get('facts', []):
                    fact = MemoryFact(
                        category=fact_data['category'],
                        key=fact_data['key'],
                        value=fact_data['value'],
                        timestamp=datetime.fromisoformat(fact_data['timestamp']),
                        metadata=fact_data.get('metadata', {})
                    )
                    
                    if fact.category not in self.facts:
                        self.facts[fact.category] = []
                    
                    self.facts[fact.category].append(fact)
                
                logger.info(f"Loaded {len(self.get_all_facts())} memory facts")
        
        except Exception as e:
            logger.error(f"Failed to load facts: {e}")
            self.facts = {}
    
    def clear(self):
        """Clear all facts."""
        self.facts = {}
        self._save_facts()
        logger.info("Cleared all memory facts")
