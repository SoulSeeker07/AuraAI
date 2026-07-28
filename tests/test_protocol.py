from aura.shared import (
    AuraMessage,
    MessageType,
    serialize,
    deserialize,
)


def test_protocol_roundtrip():
    message = AuraMessage(
        type=MessageType.WELCOME,
        source="service",
        target="desktop",
        payload={
            "message": "Welcome to Aura"
        },
    )

    encoded = serialize(message)

    decoded = deserialize(encoded)

    assert decoded.type == MessageType.WELCOME

    assert decoded.payload["message"] == "Welcome to Aura"

    assert decoded.source == "service"

    assert decoded.target == "desktop"
