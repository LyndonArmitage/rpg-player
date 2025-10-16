from abc import ABC, abstractmethod
from typing import override

import tiktoken

from rpg_player.chat_message import ChatMessage, ChatMessages


class TokenCounter(ABC):
    """
    Base class for counting tokens in messages
    """

    @abstractmethod
    def count(self, msg: ChatMessage) -> int:
        """
        Count how many tokens are in a given message
        """
        raise NotImplementedError()

    def count_all(self, msgs: ChatMessages) -> list[int]:
        """
        Count how many tokens are in all the messages
        """
        return [self.count(m) for m in msgs]

    def count_total(self, msgs: ChatMessages) -> int:
        """
        Count how many tokens are in all the messages and return the total sum
        """
        return sum(self.count_all(msgs))


class TiktokenTokenCounter(TokenCounter):
    """
    tiktoken based TokenCounter
    """

    def __init__(self, model: str):
        self.encoding: tiktoken.Encoding = tiktoken.encoding_for_model(model)
        self.encoding_name: str = tiktoken.encoding_name_for_model(model)

    @override
    def count(self, msg: ChatMessage) -> int:
        text = f"{msg.author}: {msg.content}"
        return len(self.encoding.encode(text))

    @override
    def count_all(self, msgs: ChatMessages) -> list[int]:
        encoded: list[list[int]] = self.encoding.encode_batch(
            [f"{m.author}: {m.content}" for m in msgs]
        )
        return [len(e) for e in encoded]
