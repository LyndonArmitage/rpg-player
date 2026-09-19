from collections.abc import Iterable
from typing import override

import tiktoken

from rpg_player.domain.chat_message import ChatMessage
from rpg_player.domain.token_counter import TokenCounter


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
    def count_all(self, msgs: Iterable[ChatMessage]) -> list[int]:
        encoded: list[list[int]] = self.encoding.encode_batch(
            [f"{m.author}: {m.content}" for m in msgs]
        )
        return [len(e) for e in encoded]

    @override
    def count_sum(self, msgs: Iterable[ChatMessage]) -> int:
        return sum(self.count_all(msgs))
