"""
Memory 2.0 Type Definitions

Defines all types for the intelligent memory system.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryLayer(Enum):
    """Five memory layers in Memory 2.0"""

    WORKING = "working"
    SESSION = "session"
    LONG_TERM = "long_term"
    KNOWLEDGE = "knowledge"
    WORKSPACE = "workspace"


class CategoryType(Enum):
    """Memory categories for organizing stored information"""

    PREFERENCES = "preferences"
    PROJECTS = "projects"
    PEOPLE = "people"
    SKILLS = "skills"
    GOALS = "goals"
    TASKS = "tasks"
    FILES = "files"
    DEVICES = "devices"
    NETWORKING = "networking"
    CODING = "coding"
    PERSONAL = "personal"


class ImportanceLevel(Enum):
    """Importance levels for memories"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    VITAL = 5


class RiskLevel(Enum):
    """Risk levels for sensitive operations"""

    SAFE = "safe"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryFact:
    """
    Core memory fact with intelligent metadata.

    Attributes:
        layer: Which memory layer this belongs to
        category: Category classification
        key: Unique identifier
        value: Actual memory value
        importance: How important this is
        last_accessed: When it was last used
        access_count: How many times it's been accessed
        created_at: When it was stored
        metadata: Additional context (tags, etc.)
        encrypted: Whether data is encrypted
        source: Where this memory came from
    """

    layer: MemoryLayer
    category: CategoryType
    key: str
    value: str
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    last_accessed: datetime | None = None
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    encrypted: bool = False
    source: str = "unknown"

    def __post_init__(self):
        """Validate memory structure"""
        if self.last_accessed is None:
            self.last_accessed = self.created_at

    def mark_access(self):
        """Mark as accessed and update timestamp"""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def encrypt(self, secret_key: str):
        """Encrypt the memory value"""
        if self.encrypted:
            return

        # Simple encryption (use cryptography library in production)
        self.value = self._encrypt_value(self.value, secret_key)
        self.encrypted = True

    def decrypt(self, secret_key: str) -> str:
        """Decrypt the memory value"""
        if not self.encrypted:
            return self.value

        self.value = self._encrypt_value(self.value, secret_key, decrypt=True)
        self.encrypted = False
        return self.value

    def _encrypt_value(self, value: str, secret_key: str, decrypt: bool = False) -> str:
        """Encrypt/decrypt a value"""
        if decrypt:
            # Simple XOR cipher for demo (use proper crypto in production)
            return "".join(
                chr(ord(c) ^ ord(secret_key[i % len(secret_key)]))
                for i, c in enumerate(value)
            )
        else:
            return "".join(
                chr(ord(c) ^ ord(secret_key[i % len(secret_key)]))
                for i, c in enumerate(value)
            )

    def get_hash(self) -> str:
        """Get SHA-256 hash for conflict detection"""
        content = f"{self.key}:{self.value}:{self.created_at.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            f"MemoryFact({self.layer.value}/{self.category.value}: {self.key}="
            f"{self.value[:20]}... importance={self.importance.value})"
        )


@dataclass
class MemoryAnalysisResult:
    """Result of analyzing text for memory potential"""

    should_store: bool
    importance: ImportanceLevel
    category: CategoryType
    key: str | None
    confidence: float
    metadata: dict


@dataclass
class MemoryRetrievalResult:
    """Result of memory retrieval with ranking"""

    memories: list[MemoryFact]
    score: float
    relevance: str
    context: str
    confidence: float


@dataclass
class ForgettingResult:
    """Result of forgetting operation"""

    deleted: int
    reasons: list[str]
    warnings: list[str]


@dataclass
class ConflictResult:
    """Result of conflict resolution"""

    resolved: bool
    conflict_fact: MemoryFact | None
    resolution: str
    merged_fact: MemoryFact | None


@dataclass
class MemorySummary:
    """Summary of memory state"""

    total_facts: int
    by_layer: dict[str, int]
    by_category: dict[str, int]
    by_importance: dict[int, int]
    recent_activity: list[MemoryFact]
    storage_used: str | None = None


@dataclass
class MemoryStore:
    """
    Container for all memory facts in a layer.

    Attributes:
        facts: List of memory facts
        version: Version of this store
        last_updated: When this was last updated
    """

    facts: list[MemoryFact] = field(default_factory=list)
    version: int = 1
    last_updated: datetime = field(default_factory=datetime.now)

    def _normalize_key(self, key: str) -> str:
        """Normalize key for storage"""
        import re

        key = key.lower()
        key = re.sub(r"[^\w\s-]", "", key)
        key = re.sub(r"\s+", "_", key)
        return key.strip("_")[:50]

    def add_fact(self, fact: MemoryFact):
        """Add a fact to the store"""
        # Normalize the key before adding
        fact.key = self._normalize_key(fact.key)
        self.facts.append(fact)
        self.last_updated = datetime.now()
        self.version += 1

    def get_fact(self, key: str) -> MemoryFact | None:
        """Get fact by key"""
        for fact in self.facts:
            if fact.key == key:
                fact.mark_access()
                return fact
        return None

    def get_facts_by_category(self, category: CategoryType) -> list[MemoryFact]:
        """Get all facts in a category"""
        return [f for f in self.facts if f.category == category]

    def get_facts_by_layer(self, layer: MemoryLayer) -> list[MemoryFact]:
        """Get all facts in a layer"""
        return [f for f in self.facts if f.layer == layer]

    def remove_fact(self, key: str) -> bool:
        """Remove fact by key"""
        normalized_key = self._normalize_key(key)
        for i, fact in enumerate(self.facts):
            if fact.key == normalized_key:
                self.facts.pop(i)
                return True
        return False
