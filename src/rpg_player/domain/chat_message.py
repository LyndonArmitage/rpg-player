import json
import uuid
from collections.abc import Iterable, Iterator, MutableSequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, cast, overload, override


class MessageType(StrEnum):
    """
    A type of message.

    There are 4 main types:

        - SPEECH - This is speech from an agent
        - SYSTEM - This is reserved for system prompts
        - NARRATION - This is narration from the GM/DM
        - SUMMARY - This is summaries from the system
    """

    SPEECH = "speech"
    """Speech from an agent"""
    SYSTEM = "system"
    """Reserved for system prompts"""
    NARRATION = "narration"
    """Narration from GM/DM"""
    SUMMARY = "summary"
    """Summaries from the system"""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """Domain object for  a chat message"""

    author: str = ""
    """The author of the chat message"""
    content: str = ""
    """The content of the chat message"""
    message_type: MessageType = MessageType.SPEECH
    """The message type"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """The id of the message, this should be unique"""

    @classmethod
    def speech(cls, author: str, content: str) -> Self:
        return cls(author=author, content=content, message_type=MessageType.SPEECH)

    @classmethod
    def narration(cls, author: str, content: str) -> Self:
        return cls(author=author, content=content, message_type=MessageType.NARRATION)

    @classmethod
    def system(cls, author: str, content: str) -> Self:
        return cls(author=author, content=content, message_type=MessageType.SYSTEM)

    @classmethod
    def summary(cls, author: str, content: str) -> Self:
        return cls(author=author, content=content, message_type=MessageType.SUMMARY)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    ) -> Self:
        """
        Convert from a dictionary.

        You should probably do this manually in most instances as no type
        checking is done.
        """
        return cls(**data)  # pyright: ignore[reportAny]

    # TODO: Maybe move this away from here into its own function
    def as_openai_msg(self, system_role: str = "developer") -> dict[str, str]:
        """
        Converts this message into a simple OpenAI compatible dictionary.
        """
        msg_author: str = self.author
        role = "assistant"
        match self.message_type:
            case MessageType.SPEECH:
                role = "assistant"
            case MessageType.NARRATION:
                role = "user"
            case MessageType.SYSTEM:
                role = system_role
            case MessageType.SUMMARY:
                role = "assistant"
                if msg_author == "DM" or msg_author == "GM":
                    role = "user"
        return {"role": role, "content": f"{msg_author}: {self.content}"}


class ChatMessages(MutableSequence[ChatMessage]):
    """Container for chat messages"""

    def __init__(self, messages: Iterable[ChatMessage] | None = None) -> None:
        self._messages: list[ChatMessage] = []
        if messages:
            self._messages.extend(messages)

    @property
    def messages(self) -> list[ChatMessage]:
        """A copy of the messages"""
        return self._messages.copy()

    def add_message(self, msg: ChatMessage):
        """Add a new message"""
        self.append(msg)

    def add_messages(self, msgs: Iterable[ChatMessage]):
        """Add multiple new messages"""
        self.extend(msgs)

    def filter_type(self, msg_type: MessageType) -> Iterable[ChatMessage]:
        """Get an iteration of messages that match the message type"""

        def filter_func(msg: ChatMessage) -> bool:
            return msg.message_type == msg_type

        return filter(filter_func, self._messages)

    def last(self) -> ChatMessage | None:
        """Return the last message"""
        if self._messages:
            return self._messages[-1]
        else:
            return None

    @override
    def __len__(self) -> int:
        return len(self._messages)

    @override
    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self._messages)

    @override
    def append(self, msg: ChatMessage):
        """Append the messages with a new message"""
        self._messages.append(msg)

    @override
    def extend(self, msgs: Iterable[ChatMessage]):
        """Extend the messages with additional messages"""
        self._messages.extend(msgs)

    @override
    def insert(self, index: int, value: ChatMessage):
        self._messages.insert(index, value)

    @overload
    def __getitem__(self, subscript: int) -> ChatMessage: ...

    @overload
    def __getitem__(self, subscript: slice) -> Self: ...

    @override
    def __getitem__(
        self,
        subscript: int | slice,
    ) -> ChatMessage | Self:
        if isinstance(subscript, slice):
            return type(self)(self.messages[subscript])
        return self.messages[subscript]

    @overload
    def __setitem__(
        self,
        subscript: int,
        value: ChatMessage,
    ) -> None: ...

    @overload
    def __setitem__(
        self,
        subscript: slice,
        value: Iterable[ChatMessage],
    ) -> None: ...

    @override
    def __setitem__(
        self,
        subscript: int | slice,
        value: ChatMessage | Iterable[ChatMessage],
    ) -> None:
        if isinstance(subscript, slice):
            if isinstance(value, ChatMessage):
                raise TypeError("slice assignment requires an iterable of ChatMessage")
            values = list(value)
            self._messages[subscript] = values
            return

        if not isinstance(value, ChatMessage):
            raise TypeError("integer assignment requires a ChatMessage")
        self._messages[subscript] = value

    @override
    def __delitem__(self, subscript: int | slice) -> None:
        del self._messages[subscript]


# TODO: Probably should move this somewhere else
@staticmethod
def load_messages_from_file(file: Path) -> list[ChatMessage]:
    """
    Load the given messages from a file.

    Messages should be encoded as single JSON objects per line (AKA JSONL
    or nd-json)
    """

    if not file.exists():
        return []
    loaded_messages: list[ChatMessage] = []
    with open(file, "r") as f:
        for line in f:
            trimmed = line.strip()
            entry: object = json.loads(trimmed)  # pyright: ignore[reportAny]
            message: ChatMessage = ChatMessage.from_dict(cast(dict[str, object], entry))
            loaded_messages.append(message)
    return loaded_messages
