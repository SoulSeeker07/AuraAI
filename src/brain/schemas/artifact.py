"""
Artifact — Everything Aura Creates
==================================

Responses should not be the primary output. Artifacts should.

Example:
    Research → ResearchArtifact → Verification → Response
    Engineering → CodeArtifact → Verification → Response
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Artifact:
    """An artifact created during execution."""

    artifact_id: str = field(default_factory=lambda: f"art_{uuid.uuid4().hex[:8]}")
    artifact_type: str = (
        ""  # research, code, document, file, image, voice, memory, generic
    )
    name: str = ""
    content: str = ""
    location: str = ""
    mime_type: str = "text/plain"
    creator: str = ""  # engine that created it
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "name": self.name,
            "content": self.content,
            "location": self.location,
            "mime_type": self.mime_type,
            "creator": self.creator,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


__all__ = ["Artifact"]
