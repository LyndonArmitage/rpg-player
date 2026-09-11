import logging
from collections.abc import Sequence
from typing import Any, cast, override

from openai import OpenAI
from openai.types.responses.response import Response

from rpg_player.domain.agent import Agent
from rpg_player.domain.chat_message import ChatMessage


class OpenAIAgent(Agent):
    """
    An AI Agent built using the OpenAI API.

    You will need to provide the client, the model, a name for the agent and a
    system prompt.
    """

    RESERVED_KEYS: frozenset[str] = frozenset(
        {
            "model",
            "input",
            "instructions",
            "tool_choice",
            "stream",
            "max_output_tokens",
        }
    )
    """Keyword arguments that are reserved and should not appear in extra_kwargs"""

    def __init__(
        self,
        openai: OpenAI,
        name: str,
        system_prompt: str,
        model: str = "gpt-4.1",
        max_tokens: int = 3000,
        extra_kwargs: (
            dict[str, Any] | None  # pyright: ignore[reportExplicitAny]
        ) = None,
    ):
        self.openai: OpenAI = openai
        self._name: str = name
        self.system_prompt: str = system_prompt
        self.model: str = model
        self.max_tokens: int = max_tokens
        self.system_message: str = OpenAIAgent._gen_system_message(system_prompt, name)
        self.log: logging.Logger = logging.getLogger(f"OpenAIAgent-{name}")

        extra_kwargs = extra_kwargs or {}
        intersection = OpenAIAgent.RESERVED_KEYS & extra_kwargs.keys()
        if intersection:
            raise ValueError(
                (
                    "extra_kwargs contains reserved keyword(s) "
                    f"that will be overwritten: {sorted(intersection)}"
                )
            )
        # Consolidate static params for responses.create
        self.response_kwargs: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
            "model": model,
            "instructions": self.system_message,
            "tool_choice": "none",
            "stream": False,
            "max_output_tokens": max_tokens,
        }
        self.response_kwargs.update(extra_kwargs)

    @property
    @override
    def name(self) -> str:
        return self._name

    @staticmethod
    def _gen_system_message(prompt: str, name: str) -> str:
        name_reminder = f"Your name will show up in messages as: {name}"
        return f"{prompt}\n\n{name_reminder}"

    @override
    def respond(self, messages: Sequence[ChatMessage]) -> ChatMessage:
        request_msgs: list[dict[str, str]] = list(
            map(lambda m: m.as_openai_msg(), messages)
        )

        # TODO: Tidy up the casting and pyright ignores here
        response: Response = cast(
            Response,
            self.openai.responses.create(  # pyright: ignore[reportCallIssue]
                input=request_msgs,  # pyright: ignore[reportArgumentType]
                **self.response_kwargs,
            ),
        )
        output_text = OpenAIAgent._extract_text(response)
        if not output_text:
            self.log.warning(
                "No assistant message in response; got: %s", response.output
            )
        return ChatMessage.speech(self._name, output_text)

    @staticmethod
    def _extract_text(response: Response) -> str:
        # NOTE: Previously we had to mess about with OpenAI response values as
        # it did not always provide an output_text. If this is still the case
        # then we will need to do that here.
        return response.output_text
