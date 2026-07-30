"""
Memory 2.0 Manager

Intelligent memory system with 5 layers, importance scoring, and smart retrieval.
"""

import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .memory_types import (
    MemoryFact, MemoryLayer, CategoryType, ImportanceLevel,
    MemoryAnalysisResult, MemoryRetrievalResult, ForgettingResult,
    ConflictResult, MemorySummary, MemoryStore
)
from .memory_analyzer import MemoryAnalyzer

logger = logging.getLogger(__name__)


class MemoryManagerV2:
    """
    Main Memory 2.0 orchestrator.
    
    Provides:
        - 5 memory layers (Working, Session, Long-Term, Knowledge, Workspace)
        - Importance scoring for memories
        - Category classification
        - Smart retrieval with ranking
        - Forgetting engine
        - Conflict resolution
        - Sensitive data handling
        - Integration with WorkspaceManager
    """
    
    def __init__(
        self,
        data_path: Optional[Path] = None,
        workspace_manager=None,
        secret_key: str = "default_secret_key"
    ):
        """
        Initialize Memory 2.0 Manager.
        
        Args:
            data_path: Path to store memory data
            workspace_manager: Optional WorkspaceManager for workspace-specific memories
            secret_key: Key for encrypting sensitive data
        """
        self.data_path = data_path or Path("Data/memory_2.0.json")
        self.workspace_manager = workspace_manager
        self.secret_key = secret_key
        
        # Initialize memory layers
        self.layers: Dict[MemoryLayer, MemoryStore] = {
            MemoryLayer.WORKING: MemoryStore(),
            MemoryLayer.SESSION: MemoryStore(),
            MemoryLayer.LONG_TERM: MemoryStore(),
            MemoryLayer.KNOWLEDGE: MemoryStore(),
            MemoryLayer.WORKSPACE: MemoryStore(),
        }
        
        # Load from disk
        self._load_memory()
        
        # Initialize analyzer
        self.analyzer = MemoryAnalyzer()
        
        logger.info(f"Memory 2.0 Manager initialized with {len(self.layers)} layers")
    
    async def analyze_and_remember(
        self,
        text: str,
        layer: MemoryLayer = MemoryLayer.LONG_TERM,
        source: str = "user"
    ) -> Optional[MemoryFact]:
        """
        Analyze text and store it if appropriate.
        
        Args:
            text: Text to analyze
            layer: Which layer to store in
            source: Source of the memory
        
        Returns:
            Stored MemoryFact or None
        """
        # Analyze the text
        analysis = await self.analyzer.analyze(text)
        
        if not analysis.should_store:
            logger.debug(f"Not storing: {text[:50]}... reason: {analysis.metadata.get('reason')}")
            return None
        
        # Get values from the analysis
        normalized_key = analysis.key
        category = analysis.category
        importance = analysis.importance
        value = text  # Use the full text as the value
        metadata = analysis.metadata
        
        # Check if memory with this key already exists in the layer
        existing_fact = self.layers[layer].get_fact(normalized_key)
        logger.debug(f"Checking for existing fact with key '{normalized_key}': {existing_fact is not None}")
        if existing_fact:
            logger.debug(f"Updating existing fact: value was '{existing_fact.value}', now '{value}'")
        else:
            logger.debug(f"Creating new fact with key '{normalized_key}'")
        
        # Create or update the memory fact
        if existing_fact:
            # Update existing memory
            existing_fact.value = value
            existing_fact.importance = importance
            existing_fact.last_accessed = datetime.now()
            existing_fact.access_count += 1
            existing_fact.category = category
            existing_fact.metadata = metadata or {}
            existing_fact.source = "manual"
            fact = existing_fact
            logger.info(f"Updated memory: {layer.value}/{category.value}/{normalized_key}")
        else:
            # Create new memory fact
            fact = MemoryFact(
                layer=layer,
                category=category,
                key=normalized_key,
                value=value,
                importance=importance,
                metadata=metadata or {},
                source="manual"
            )

        # Encrypt if sensitive data is detected in metadata
        if metadata and metadata.get('contains_sensitive'):
            fact.encrypt(self.secret_key)
            logger.info(f"Encrypted sensitive memory: {layer.value}/{category.value}/{normalized_key}")

        # Encrypt if needed
            fact.encrypt(self.secret_key)
        
        # Store in the appropriate layer
        self.layers[layer].add_fact(fact)
        
        # Save to disk
        self._save_memory()
        
        logger.info(
            f"Stored memory: {layer.value}/{analysis.category.value}/{analysis.key} "
            f"(importance={analysis.importance.value})"
        )
        
        return fact
    
    async def remember(
        self,
        key: str,
        value: str,
        category: CategoryType = CategoryType.PERSONAL,
        layer: MemoryLayer = MemoryLayer.LONG_TERM,
        importance: ImportanceLevel = ImportanceLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
        encrypt: bool = False
    ) -> Optional[MemoryFact]:
        """
        Manually store a memory fact.
        
        Args:
            key: Unique key for the fact
            value: Value to store
            category: Category of the fact
            layer: Which layer to store in
            importance: Importance level
            metadata: Additional metadata
            encrypt: Whether to encrypt the value
        
        Returns:
            Stored MemoryFact or None
        """
        # Normalize key to match format used by analyze_and_remember()
        normalized_key = self.analyzer._normalize_key(key) if key else "general"
        
        # Check if memory with this key already exists in the layer
        existing_fact = self.layers[layer].get_fact(normalized_key)
        
        # Create or update the memory fact
        if existing_fact:
            # Update existing memory
            existing_fact.value = value
            existing_fact.importance = importance
            existing_fact.last_accessed = datetime.now()
            existing_fact.access_count += 1
            existing_fact.category = category
            existing_fact.metadata = metadata or {}
            existing_fact.source = "manual"
            fact = existing_fact
            logger.info(f"Updated memory: {layer.value}/{category.value}/{normalized_key}")
        else:
            # Create new memory fact
            fact = MemoryFact(
                layer=layer,
                category=category,
                key=normalized_key,
                value=value,
                importance=importance,
                metadata=metadata or {},
                source="manual"
            )
            if encrypt:
                fact.encrypt(self.secret_key)
            self.layers[layer].add_fact(fact)
            logger.info(f"Stored memory: {layer.value}/{category.value}/{normalized_key}")
        
        self._save_memory()
        
        return fact
    
    def retrieve(
        self,
        category: Optional[CategoryType] = None,
        layer: Optional[MemoryLayer] = None,
        key: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryFact]:
        """
        Retrieve memories based on criteria.
        
        Args:
            category: Filter by category
            layer: Filter by layer
            key: Get specific fact by key
            limit: Maximum number of results
        
        Returns:
            List of matching memories
        """
        memories = []

        # Get facts from appropriate layer(s)
        if layer:
            # If layer is specified but category is None, get all facts from that layer
            if category is None:
                memories = self.layers[layer].facts.copy()
            else:
                memories = self.layers[layer].get_facts_by_category(category)
        elif category:
            for mem_layer in self.layers.values():
                memories.extend(mem_layer.get_facts_by_category(category))
        else:
            for mem_layer in self.layers.values():
                memories.extend(mem_layer.facts)

        # Filter by key if specified (normalize key first)
        if key:
            normalized_key = self.analyzer._normalize_key(key) if key else None
            if normalized_key:
                memories = [m for m in memories if m.key == normalized_key]
        
        # Limit results
        memories = memories[:limit]
        
        # Sort by importance and last accessed
        memories.sort(key=lambda f: (f.importance.value, -f.access_count), reverse=True)
        
        return memories
    
    async def retrieve_with_reranking(
        self,
        query: str,
        layers: Optional[List[MemoryLayer]] = None,
        limit: int = 10
    ) -> MemoryRetrievalResult:
        """
        Retrieve memories and rerank based on query relevance.
        
        Args:
            query: Query to match against memories
            layers: Which layers to search (default: all)
            limit: Maximum number of results
        
        Returns:
            MemoryRetrievalResult with ranked memories
        """
        # Get all memories from specified layers
        memories = []
        if layers:
            for layer in layers:
                memories.extend(self.layers[layer].facts)
        else:
            for layer in self.layers.values():
                memories.extend(layer.facts)
        
        # Simple keyword-based relevance scoring
        query_lower = query.lower()
        words = set(query_lower.split())
        
        scored_memories = []
        for memory in memories:
            score = 0
            # Check if query keywords appear in memory
            memory_lower = memory.value.lower()
            for word in words:
                if word in memory_lower:
                    score += 1
            
            # Boost by importance
            score += memory.importance.value * 0.5
            
            # Boost by access frequency (used memories are more relevant)
            score += memory.access_count * 0.1
            
            if score > 0:
                scored_memories.append((memory, score))
        
        # Sort by score and return top results
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        top_memories = [mem for mem, score in scored_memories[:limit]]
        top_scores = [score for mem, score in scored_memories[:limit]]
        
        # Build context
        context = self._build_context(top_memories)
        
        return MemoryRetrievalResult(
            memories=top_memories,
            score=sum(top_scores) / len(top_scores) if top_scores else 0,
            relevance=f"Based on {len(query_lower.split())} keyword matches",
            context=context,
            confidence=1.0
        )
    
    def forget(
        self,
        key: str,
        layer: Optional[MemoryLayer] = None,
        confirm: bool = True
    ) -> ForgettingResult:
        """
        Remove a memory by key.
        
        Args:
            key: Key of the memory to forget
            layer: Which layer to remove from (default: all)
            confirm: Whether to ask for confirmation
        
        Returns:
            ForgettingResult with details
        """
        deleted = 0
        reasons = []
        warnings = []

        # Normalize key before searching
        normalized_key = self.analyzer._normalize_key(key) if key else key

        if layer:
            # Remove from single layer
            if self.layers[layer].remove_fact(normalized_key):
                deleted += 1
                reasons.append(f"Removed from {layer.value}")
        else:
            # Remove from all layers
            for mem_layer in self.layers.values():
                if mem_layer.remove_fact(normalized_key):
                    deleted += 1
                    reasons.append(f"Removed from {mem_layer.__class__.__name__}")
        
        if deleted == 0:
            warnings.append(f"Memory with key '{key}' not found")
        
        self._save_memory()
        
        return ForgettingResult(
            deleted=deleted,
            reasons=reasons,
            warnings=warnings
        )
    
    async def forget_old_memories(
        self,
        days: int = 30,
        importance_threshold: ImportanceLevel = ImportanceLevel.LOW
    ) -> ForgettingResult:
        """
        Automatically forget old and unimportant memories.
        
        Args:
            days: Maximum age of memory in days
            importance_threshold: Minimum importance to keep
        
        Returns:
            ForgettingResult with details
        """
        deleted = 0
        reasons = []
        warnings = []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for mem_layer in self.layers.values():
            facts_to_remove = []
            for fact in mem_layer.facts:
                # Remove if too old and not important enough
                if (fact.created_at < cutoff_date and 
                    fact.importance.value <= importance_threshold.value):
                    facts_to_remove.append(fact)
            
            for fact in facts_to_remove:
                mem_layer.remove_fact(fact.key)
                deleted += 1
                reasons.append(
                    f"Forgot {fact.layer.value}/{fact.category.value}/{fact.key} "
                    f"(old: {cutoff_date.date()})"
                )
        
        if deleted > 0:
            warnings.append("Automatically cleaned up old memories")
        
        self._save_memory()
        
        return ForgettingResult(
            deleted=deleted,
            reasons=reasons,
            warnings=warnings
        )
    
    def resolve_conflict(
        self,
        key: str,
        new_value: str,
        layer: MemoryLayer = MemoryLayer.LONG_TERM
    ) -> ConflictResult:
        """
        Resolve conflict between existing and new memory value.
        
        Args:
            key: Key of the conflicting memory
            new_value: New value to store
            layer: Which layer to resolve in
        
        Returns:
            ConflictResult with resolution
        """
        # Normalize key before searching
        normalized_key = self.analyzer._normalize_key(key) if key else key

        # Get existing fact
        existing_fact = self.layers[layer].get_fact(normalized_key)
        
        if existing_fact is None:
            # No conflict, just store the new value
            return ConflictResult(
                resolved=True,
                conflict_fact=None,
                resolution="No conflict - new value stored",
                merged_fact=None
            )
        
        # Compare values
        if existing_fact.value == new_value:
            # Same value, nothing to do
            return ConflictResult(
                resolved=True,
                conflict_fact=existing_fact,
                resolution="No change needed - values are identical",
                merged_fact=existing_fact
            )
        
        # Conflict detected - decide how to resolve
        # Simple rule: newer memory gets higher importance
        new_fact = MemoryFact(
            layer=layer,
            category=existing_fact.category,
            key=key,
            value=new_value,
            importance=ImportanceLevel.HIGH,  # Promote to HIGH for updates
            created_at=datetime.now(),
            metadata={"updated": True, "original": existing_fact.value},
            source="update"
        )
        
        # Keep the access count and last accessed
        new_fact.access_count = existing_fact.access_count
        new_fact.last_accessed = existing_fact.last_accessed
        
        # Remove old fact, add new one
        self.layers[layer].remove_fact(key)
        self.layers[layer].add_fact(new_fact)
        
        return ConflictResult(
            resolved=True,
            conflict_fact=existing_fact,
            resolution=f"Updated: '{existing_fact.value}' → '{new_value}'",
            merged_fact=new_fact
        )
    
    def get_summary(self) -> MemorySummary:
        """
        Get a summary of memory state.
        
        Returns:
            MemorySummary with statistics
        """
        total_facts = sum(len(layer.facts) for layer in self.layers.values())
        
        by_layer = {}
        by_category = {}
        by_importance = {i.value: 0 for i in ImportanceLevel}
        
        for layer in self.layers.values():
            # By layer
            layer_name = layer.__class__.__name__
            by_layer[layer_name] = len(layer.facts)
            
            # By category
            for fact in layer.facts:
                cat_name = fact.category.value
                by_category[cat_name] = by_category.get(cat_name, 0) + 1
                
                # By importance
                by_importance[fact.importance.value] += 1
        
        # Get recent activity (last 5 accessed)
        all_facts = []
        for layer in self.layers.values():
            all_facts.extend(layer.facts)
        
        all_facts.sort(key=lambda f: f.last_accessed, reverse=True)
        recent_activity = all_facts[:5]
        
        # Storage used (estimate)
        storage_used = self._estimate_storage()
        
        return MemorySummary(
            total_facts=total_facts,
            by_layer=by_layer,
            by_category=by_category,
            by_importance=by_importance,
            recent_activity=recent_activity,
            storage_used=storage_used
        )
    
    def get_context(self, limit: int = 10) -> str:
        """
        Get formatted memory context string.
        
        Args:
            limit: Maximum number of facts to include
        
        Returns:
            Formatted context string
        """
        all_facts = []
        for layer in self.layers.values():
            all_facts.extend(layer.facts)
        
        # Sort by importance and last accessed
        all_facts.sort(
            key=lambda f: (f.importance.value, -f.access_count, f.last_accessed),
            reverse=True
        )
        
        # Format context
        lines = []
        for fact in all_facts[:limit]:
            line = f"{fact.layer.value}/{fact.category.value}: {fact.key} = {fact.value[:50]}"
            if fact.encrypted:
                line += " [ENCRYPTED]"
            lines.append(line)
        
        if not lines:
            return "No memories stored yet."
        
        return "\n".join(lines)
    
    def _build_context(self, memories: List[MemoryFact]) -> str:
        """Build context string from memories."""
        lines = []
        for fact in memories:
            line = f"{fact.category.value}: {fact.key} = {fact.value[:50]}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _estimate_storage(self) -> Optional[str]:
        """Estimate storage used by memory."""
        try:
            total_bytes = 0
            for layer in self.layers.values():
                for fact in layer.facts:
                    # Estimate size (value + metadata)
                    total_bytes += len(fact.value.encode()) + 100
            
            if total_bytes > 1024 * 1024:
                return f"{total_bytes / (1024 * 1024):.1f} MB"
            elif total_bytes > 1024:
                return f"{total_bytes / 1024:.1f} KB"
            else:
                return f"{total_bytes} B"
        except Exception:
            return None
    
    def _save_memory(self):
        """Save memory state to disk."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': '2.0',
                'saved_at': datetime.now().isoformat(),
                'layers': {}
            }
            
            for layer, store in self.layers.items():
                layer_data = {
                    'version': store.version,
                    'last_updated': store.last_updated.isoformat(),
                    'facts': []
                }
                
                for fact in store.facts:
                    fact_data = {
                        'layer': layer.value,
                        'category': fact.category.value,
                        'key': fact.key,
                        'value': fact.value,
                        'importance': fact.importance.value,
                        'last_accessed': fact.last_accessed.isoformat(),
                        'access_count': fact.access_count,
                        'created_at': fact.created_at.isoformat(),
                        'metadata': fact.metadata,
                        'encrypted': fact.encrypted,
                        'source': fact.source
                    }
                    layer_data['facts'].append(fact_data)
                
                data['layers'][layer.value] = layer_data
            
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Memory state saved to {self.data_path}")
        
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def _load_memory(self):
        """Load memory state from disk."""
        try:
            if not self.data_path.exists():
                logger.info("No existing memory data found, starting fresh")
                return
            
            with open(self.data_path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loading memory data from {self.data_path}")
            
            for layer_name, layer_data in data.get('layers', {}).items():
                layer = MemoryLayer(layer_name)
                store = self.layers[layer]
                
                for fact_data in layer_data.get('facts', []):
                    fact = MemoryFact(
                        layer=layer,
                        category=CategoryType(fact_data['category']),
                        key=fact_data['key'],
                        value=fact_data['value'],
                        importance=ImportanceLevel(fact_data['importance']),
                        last_accessed=datetime.fromisoformat(fact_data['last_accessed']),
                        access_count=fact_data['access_count'],
                        created_at=datetime.fromisoformat(fact_data['created_at']),
                        metadata=fact_data.get('metadata', {}),
                        encrypted=fact_data.get('encrypted', False),
                        source=fact_data.get('source', 'unknown')
                    )
                    store.add_fact(fact)
            
            logger.info(f"Loaded {len(self.layers)} layers with "
                       f"{sum(len(s.facts) for s in self.layers.values())} facts")
        
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            # Start fresh on error
            self._init_empty_memory()
    
    def _init_empty_memory(self):
        """Initialize empty memory stores."""
        self.layers = {
            MemoryLayer.WORKING: MemoryStore(),
            MemoryLayer.SESSION: MemoryStore(),
            MemoryLayer.LONG_TERM: MemoryStore(),
            MemoryLayer.KNOWLEDGE: MemoryStore(),
            MemoryLayer.WORKSPACE: MemoryStore(),
        }
