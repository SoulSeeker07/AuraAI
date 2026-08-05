import json

from .exceptions import AuraProtocolError
from .message import AuraMessage


def serialize(message: AuraMessage) -> str:
    return message.model_dump_json()


def deserialize(data: str) -> AuraMessage:
    try:
        obj = json.loads(data)
        return AuraMessage.model_validate(obj)

    except Exception as exc:
        raise AuraProtocolError(str(exc)) from exc
