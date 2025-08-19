import enum
import uuid
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional


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

    @staticmethod
    def from_dict(d: dict) -> "ChatMessage":
        return ChatMessage(
            d["msg_id"], d["author"], MessageType(d["type"]), d["content"]
        )

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "author": self.author,
            "type": self.type.value,
            "content": self.content,
        }


class ChatMessages:
    """
    Container class for messages.

    This will contain all messages sent during a session.
    """

    @staticmethod
    def convert_to_openai(message: ChatMessage) -> dict:
        role = "assistant"
        match message.type:
            case MessageType.SPEECH:
                role = "assistant"
            case MessageType.NARRATION:
                role = "user"
            case MessageType.SYSTEM:
                role = "developer"
        return {"role": role, "content": message.content}

    def __init__(self):
        self.messages: List[ChatMessage] = []
        # This is to reduce the creation of OpenAI style messages
        self._openai_messages: List[dict] = []

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self.messages)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return list(self.messages)[idx]
        return list(self.messages)[idx]

    def append(self, message: ChatMessage):
        self.messages.append(message)
        openai_msg = ChatMessages.convert_to_openai(message)
        self._openai_messages.append(openai_msg)

    def extend(self, messages: Iterable[ChatMessage]):
        for message in messages:
            self.append(message)

    @property
    def as_openai(self) -> List[dict]:
        return self._openai_messages

    @property
    def last(self) -> Optional[ChatMessage]:
        if self.messages:
            return self.messages[-1]
        else:
            return None
