from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ai.models import ChatMessage, ImageAttachment
from Memory import MemoryFact

IntentName = Literal[
    "local_time",
    "memory_summary",
    "profile_lookup",
    "projects_lookup",
    "skills_lookup",
    "goals_lookup",
    "preferences_lookup",
    "capability_status",
    "remember_fact",
    "vision",
    "web_search",
    "provider_chat",
    "deep_research",
]


@dataclass(frozen=True)
class ConversationAttachment:
    path: Path
    mime_type: str = "application/octet-stream"


@dataclass(frozen=True)
class Intent:
    name: IntentName
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationContext:
    user_input: str
    intent: Intent
    messages: list[ChatMessage]
    attachments: list[ConversationAttachment] = field(default_factory=list)
    memory: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    web_results: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationResult:
    text: str
    intent: Intent
    used_provider: bool = False
    provider: str | None = None
    model: str | None = None
    remembered_facts: list[MemoryFact] = field(default_factory=list)


def image_attachment_from_conversation(
    attachment: ConversationAttachment,
) -> ImageAttachment:
    return ImageAttachment(path=attachment.path, mime_type=attachment.mime_type)


# Deep Research Models
@dataclass(frozen=True)
class WebSearchResultSimple:
    """Simple web search result for compatibility."""

    title: str
    url: str
    snippet: str
    score: float = 0.0


WebSearchResult = WebSearchResultSimple


@dataclass(frozen=True)
class ResearchFinding:
    """A finding from deep research."""

    source_title: str
    source_url: str
    source_authority: float
    key_points: list[str]
    confidence: float
    additional_notes: str = ""


@dataclass(frozen=True)
class DeepResearchResult:
    """Complete deep research result."""

    query: str
    main_results: list[dict[str, Any]]
    top_sources: list[Any]  # RankedResult objects
    page_contents: list[Any]  # PageContent objects
    citations: list[Any]  # Citation objects
    key_findings: list[ResearchFinding]
    comparison_data: dict[str, Any]
    confidence_score: float
    processing_time: float
    estimated_duration: str
