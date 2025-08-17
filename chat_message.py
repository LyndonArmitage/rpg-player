import enum
import uuid
from dataclasses import dataclass, field


class MessageType(enum.Enum):
    """
    A type of message.

    There are 3 main types, only 2 of which will likely be used often.
    """

    SPEECH = "speech"
    SYSTEM = "system"
    NARRATION = "narration"


@dataclass
class ChatMessage:
    msg_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )  # A unique ID for the message
    author: str = ""  # The author of the message
    type: MessageType = MessageType.SPEECH  # The message type
    content: str = ""  # The content of the message, should be plain text

    @classmethod
    def speech(cls, author: str, content: str) -> "ChatMessage":
        return cls(str(uuid.uuid4()), author, MessageType.SPEECH, content)

    @classmethod
    def narration(cls, author: str, content: str) -> "ChatMessage":
        return cls(str(uuid.uuid4()), author, MessageType.NARRATION, content)

    @classmethod
    def system(cls, author: str, content: str) -> "ChatMessage":
        return cls(str(uuid.uuid4()), author, MessageType.SYSTEM, content)
