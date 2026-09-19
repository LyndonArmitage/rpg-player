from collections.abc import Sequence
from typing import Protocol

from rpg_player.domain.chat_message import ChatMessage


class Agent(Protocol):
    """Base protocol for agents"""

    @property
    def name(self) -> str:
        """The name of the agent"""
        ...

    def respond(self, messages: Sequence[ChatMessage]) -> ChatMessage:
        """
        Given the current messages, generate a response
        """
        ...
