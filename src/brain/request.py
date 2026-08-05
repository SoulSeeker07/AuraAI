"""
AuraBrain Request Models

Defines the unified request/response models for Aura.
Everything enters AuraBrain through these models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RequestSource(str, Enum):
    """Source of the request."""

    CHAT = "chat"
    VOICE = "voice"
    VISION = "vision"
    PLUGIN = "plugin"
    API = "api"
    AUTOMATION = "automation"


class ResponseStatus(str, Enum):
    """Status of the response."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


class ActionType(str, Enum):
    """Type of action Aura can take."""

    MEMORY = "memory"
    TOOL = "tool"
    PROVIDER = "provider"
    VISION = "vision"
    VOICE = "voice"
    AGENT = "agent"
    UNKNOWN = "unknown"


@dataclass
class ConversationAttachment:
    """An attachment to a request."""

    path: Path
    mime_type: str = "application/octet-stream"
    description: str | None = None


@dataclass
class AuraRequest:
    """
    Unified request from any external source.

    Everything enters AuraBrain through this model.
    """

    text: str
    source: RequestSource = RequestSource.CHAT
    attachments: list[ConversationAttachment] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate and normalize request."""
        if self.conversation_id is None:
            self.conversation_id = str(uuid4())
        self.text = self.text.strip()

    @property
    def has_attachments(self) -> bool:
        """Check if request has attachments."""
        return len(self.attachments) > 0

    @property
    def is_complex(self) -> bool:
        """Check if request is complex (needs planning)."""
        word_count = len(self.text.split())
        return word_count > 10 or any(
            word in self.text.lower()
            for word in ["create", "build", "automate", "analyze", "summarize"]
        )

    @property
    def is_multimodal(self) -> bool:
        """Check if request is multimodal (voice + text)."""
        return self.source == RequestSource.VOICE and self.has_attachments


@dataclass
class ToolResult:
    """Result of executing a tool."""

    tool_name: str
    success: bool
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Tool result is truthy if successful."""
        return self.success


@dataclass
class ExecutionResult:
    """Result of executing a decision."""

    text: str
    action_type: ActionType
    tool_results: list[ToolResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    thinking: str = ""
    execution_time: float = 0.0

    def add_tool_result(self, result: ToolResult):
        """Add a tool result."""
        self.tool_results.append(result)
        if not result.success:
            self.errors.append(f"Tool {result.tool_name} failed: {result.error}")

    @property
    def success(self) -> bool:
        """Result is successful if all tools succeeded and no errors."""
        return all(tool.success for tool in self.tool_results) and len(self.errors) == 0

    @property
    def has_tools(self) -> bool:
        """Check if tool results exist."""
        return len(self.tool_results) > 0


@dataclass
class AuraResponse:
    """
    Unified response from AuraBrain.

    Everything returns through this model.
    """

    text: str
    status: ResponseStatus
    execution_time: float = 0.0
    tool_results: list[ToolResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_id: str = ""

    @property
    def has_tools(self) -> bool:
        """Check if tool results exist."""
        return len(self.tool_results) > 0

    @property
    def is_error(self) -> bool:
        """Check if response has errors."""
        return self.status == ResponseStatus.ERROR

    @property
    def is_partial(self) -> bool:
        """Check if response is partial (some tools failed)."""
        return self.status == ResponseStatus.PARTIAL
