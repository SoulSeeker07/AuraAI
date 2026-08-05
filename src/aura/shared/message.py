from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import MessageType


class AuraMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))

    type: MessageType

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source: str

    target: str

    payload: dict = Field(default_factory=dict)
