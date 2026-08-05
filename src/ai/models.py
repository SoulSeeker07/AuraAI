from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class ImageAttachment:
    path: Path
    mime_type: str = "image/png"


@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisionRequest:
    prompt: str
    image: ImageAttachment
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 700


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider: str
    model: str


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str
    default_model: str
    supports_streaming: bool = False
    supports_vision: bool = False
    supports_tools: bool = False
    supports_images: bool = False
    token_limit: int | None = None
