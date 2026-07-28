from uuid import uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .enums import MessageType


class AuraMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))

    type: MessageType

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    source: str

    target: str

    payload: dict = Field(default_factory=dict)
