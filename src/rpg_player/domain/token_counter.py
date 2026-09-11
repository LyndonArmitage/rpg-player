from collections.abc import Iterable
from typing import Protocol

from rpg_player.domain.chat_message import ChatMessage


class TokenCounter(Protocol):
    """Base protocol for counting tokens in messages"""

    def count(self, msg: ChatMessage) -> int:
        """Count the number of tokens in a chat message"""
        ...

    def count_all(self, msgs: Iterable[ChatMessage]) -> list[int]:
        """
        Count all the tokens in a collection of chat messages.

        This function is a convenience in case the token counter can batch.
        """
        ...

    def count_sum(self, msgs: Iterable[ChatMessage]) -> int:
        """
        Count all the tokens in a collection of chat messages and sum them
        together.

        This function is a convenience in case the token counter can batch.
        """
        ...
