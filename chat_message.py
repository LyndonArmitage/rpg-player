import enum
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, List, Optional


class MessageType(enum.Enum):
    """
    A type of message.

    There are 4 main types:

        - SPEECH - This is speech from an agent
        - SYSTEM - This is reserved for system prompts
        - NARRATION - This is narration from the GM/DM
        - SUMMARY - This is summaries from the system
    """

    SPEECH = "speech"
    SYSTEM = "system"
    NARRATION = "narration"
    SUMMARY = "summary"


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

    @classmethod
    def summary(cls, author: str, content: str) -> "ChatMessage":
        return cls(str(uuid.uuid4()), author, MessageType.SUMMARY, content)

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
        msg_author: str = message.author
        role = "assistant"
        match message.type:
            case MessageType.SPEECH:
                role = "assistant"
            case MessageType.NARRATION:
                role = "user"
            case MessageType.SYSTEM:
                role = "developer"
            case MessageType.SUMMARY:
                role = "assistant"
                if msg_author == "DM" or msg_author == "GM":
                    role = "user"
        return {"role": role, "content": f"{msg_author}: {message.content}"}

    @staticmethod
    def load_messages_from_file(file: Path) -> List[ChatMessage]:
        """
        Load the given messages from a file.

        Messages should be encoded as single JSON objects per line (AKA JSONL
        or nd-json)
        """
        if not file.exists():
            return []
        loaded_messages: List[ChatMessage] = []
        with open(file, "r") as f:
            for line in f:
                trimmed = line.strip()
                entry = json.loads(trimmed)
                message: ChatMessage = ChatMessage.from_dict(entry)
                loaded_messages.append(message)
        return loaded_messages

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

    def filter_type(self, msg_type: MessageType) -> List[ChatMessage]:
        msgs: List[ChatMessage] = []
        for message in self.messages:
            if message.type == msg_type:
                msgs.append(message)
        return msgs

    @property
    def as_openai(self) -> List[dict]:
        return self._openai_messages

    @property
    def last(self) -> Optional[ChatMessage]:
        if self.messages:
            return self.messages[-1]
        else:
            return None
