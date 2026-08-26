"""
Cognitive Memory Data Models
Location: src/memory/models.py

Defines the unified MemoryItem model, MemoryType enum, and MemoryProvenance
for Milestone 17 Cognitive Memory System.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Supported cognitive memory types."""

    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PREFERENCE = "preference"
    PROJECT = "project"
    TASK = "task"


class ProvenanceSource(str, Enum):
    """Source types for memory provenance tracking."""

    USER_EXPLICIT = "user_explicit"
    CONVERSATION = "conversation"
    RUNTIME_SESSION = "runtime_session"
    EXECUTION_RESULT = "execution_result"
    IMPORTED = "imported"
    CLAUDE_IMPORT = "claude_import"
    CHATGPT_IMPORT = "chatgpt_import"
    INFERRED = "inferred"


@dataclass
class MemoryProvenance:
    """Tracks origin and verification metadata for memories."""

    source_type: ProvenanceSource = ProvenanceSource.USER_EXPLICIT
    source_id: str = ""
    confidence: float = 1.0
    verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value if isinstance(self.source_type, Enum) else str(self.source_type),
            "source_id": self.source_id,
            "confidence": self.confidence,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryProvenance":
        st = data.get("source_type", "user_explicit")
        try:
            source_enum = ProvenanceSource(st)
        except ValueError:
            source_enum = ProvenanceSource.USER_EXPLICIT
        return cls(
            source_type=source_enum,
            source_id=data.get("source_id", ""),
            confidence=data.get("confidence", 1.0),
            verified=data.get("verified", True),
        )


@dataclass
class MemoryItem:
    """
    Unified MemoryItem dataclass representing a single cognitive memory record.
    """

    content: str
    type: MemoryType = MemoryType.LONG_TERM
    memory_id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    provenance: MemoryProvenance = field(default_factory=MemoryProvenance)
    created_at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    importance: float = 0.5  # 0.0 to 1.0
    confidence: float = 1.0   # 0.0 to 1.0
    project_id: str = "global"
    topic: str = "general"
    access_count: int = 0
    last_accessed: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "type": self.type.value if isinstance(self.type, Enum) else str(self.type),
            "content": self.content,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "importance": self.importance,
            "confidence": self.confidence,
            "project_id": self.project_id,
            "topic": self.topic,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryItem":
        mt = data.get("type", "long_term")
        try:
            type_enum = MemoryType(mt)
        except ValueError:
            type_enum = MemoryType.LONG_TERM

        prov_data = data.get("provenance", {})
        prov = MemoryProvenance.from_dict(prov_data) if isinstance(prov_data, dict) else MemoryProvenance()

        return cls(
            memory_id=data.get("memory_id", f"mem_{uuid.uuid4().hex[:12]}"),
            type=type_enum,
            content=data.get("content", ""),
            provenance=prov,
            created_at=data.get("created_at", dt.datetime.now().isoformat(timespec="seconds")),
            updated_at=data.get("updated_at", dt.datetime.now().isoformat(timespec="seconds")),
            importance=data.get("importance", 0.5),
            confidence=data.get("confidence", 1.0),
            project_id=data.get("project_id", "global"),
            topic=data.get("topic", "general"),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", dt.datetime.now().isoformat(timespec="seconds")),
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {}),
        )
