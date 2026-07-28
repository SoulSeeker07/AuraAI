from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    timestamp: str = Field(default_factory=now_iso)
    source: Optional[str] = None
    target: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "forbid"


__all__ = ["Message", "now_iso"]
