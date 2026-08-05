from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    timestamp: str = Field(default_factory=now_iso)
    source: str | None = None
    target: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "forbid"


__all__ = ["Message", "now_iso"]
