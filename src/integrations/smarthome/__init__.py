"""Smart home integration package."""
from .ha_client import (
    HAConnectionError,
    HAWebSocketClient,
    HomeAssistantClient,
    VerifiedCommandResult,
    state_matches,
)

__all__ = [
    "HAConnectionError",
    "HAWebSocketClient",
    "HomeAssistantClient",
    "VerifiedCommandResult",
    "state_matches",
]
