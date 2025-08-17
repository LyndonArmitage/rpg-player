import enum
from dataclasses import dataclass


class MessageType(enum.Enum):
    SPEECH = "speech"
    SYSTEM = "system"
    NARRATION = "narration"


@dataclass
class ChatMessage:
    id: str
    author: str
    type: MessageType
    content: str
