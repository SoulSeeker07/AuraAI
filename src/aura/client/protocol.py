"""Protocol helpers for building and parsing Aura messages."""
from __future__ import annotations

import json
from typing import Dict, Any
from .message import Message
from loguru import logger


def build_message(msg_type: str, payload: Dict[str, Any], source: str = "desktop", target: str = "service") -> Dict[str, Any]:
    m = Message(type=msg_type, payload=payload, source=source, target=target)
    return m.model_dump()


def parse_message(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
        # validate via Message if possible
        msg = Message.model_validate(data)
        return msg.model_dump()
    except Exception as e:
        logger.debug("Failed to parse message: {}", e)
        # return a raw wrapper
        return {"type": "raw", "raw": raw}
