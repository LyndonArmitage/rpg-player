from collections.abc import Sequence
from typing import override

from rpg_player.domain.agent import Agent
from rpg_player.domain.chat_message import ChatMessage


class DummyAgent(Agent):
    """
    A dummy AI Agent that always returns a given message
    """

    def __init__(self, name: str, message: str):
        self._name: str = name
        self.message: str = message

    @property
    @override
    def name(self) -> str:
        return self._name

    @override
    def respond(self, messages: Sequence[ChatMessage]) -> ChatMessage:
        return ChatMessage.speech(self._name, self.message)
