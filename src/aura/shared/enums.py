from enum import Enum


class MessageType(str, Enum):
    WELCOME = "welcome"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"

    CHAT_MESSAGE = "chat.message"
    CHAT_RESPONSE = "chat.response"

    NOTIFICATION = "notification"

    ERROR = "error"

    SHUTDOWN = "shutdown"
