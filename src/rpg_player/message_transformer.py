from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import replace
from typing import override

from rpg_player.domain.chat_message import ChatMessage


class ChatMessageTransformer(ABC):
    """
    Base class for classes that can do additional transformations to generated
    chat messages.

    These transformations could be as simple as removing mistakes LLMs might
    have made or censoring words, and as complicated as running the generated
    text through code to generate speech tags for audio models.
    """

    @abstractmethod
    def transform(self, message: ChatMessage) -> ChatMessage:
        raise NotImplementedError


class NoOpMessageTranformer(ChatMessageTransformer):
    """
    A message transformer class that does nothing
    """

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        return message


class SequentialMessageTransformer(ChatMessageTransformer):
    """
    A message transformer that will apply multiple other transformers in
    sequence
    """

    def __init__(self, transformers: Iterable[ChatMessageTransformer]) -> None:
        self.transformers: list[ChatMessageTransformer] = list(transformers)

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        response: ChatMessage = message
        for transformer in self.transformers:
            response = transformer.transform(response)
        return response


class RemovePrefixMessageTransformer(ChatMessageTransformer):
    """
    Message transformer that strips the author prefix if it appears at the
    start of the message.
    """

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        prefix: str = f"{message.author}:"
        if message.content.startswith(prefix):
            new_content = (message.content[len(prefix) :]).strip()
            return replace(message, content=new_content)
        return message
