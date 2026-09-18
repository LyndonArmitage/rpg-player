import logging
from collections.abc import Sequence
from typing import Literal, override

from openai import Omit, OpenAI
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseInputItemParam,
    ResponseInputParam,
)
from openai.types.responses.response import Response
from openai.types.shared_params.reasoning import Reasoning

from rpg_player.domain.agent import Agent
from rpg_player.domain.chat_message import ChatMessage, MessageType


class OpenAIAgent(Agent):
    """
    An AI Agent built using the OpenAI API.

    You will need to provide the client, the model, a name for the agent and a
    system prompt.
    """

    def __init__(
        self,
        openai: OpenAI,
        name: str,
        system_prompt: str,
        model: str = "gpt-5.6-luna",
        max_output_tokens: int = 3000,
        reasoning_effort: Reasoning | None = None,
        system_role: Literal["developer", "system"] = "developer",
    ):
        self.openai: OpenAI = openai
        self._name: str = name
        self.system_prompt: str = system_prompt
        self.model: str = model
        self.max_tokens: int = max_output_tokens
        self.system_message: EasyInputMessageParam = OpenAIAgent._gen_system_message(
            system_role, system_prompt, name
        )
        self.log: logging.Logger = logging.getLogger(f"OpenAIAgent-{name}")
        self.reasoning: Reasoning | None = (
            reasoning_effort if reasoning_effort else Reasoning(effort="low")
        )
        self.system_role: Literal["developer", "system"] = system_role

    @property
    @override
    def name(self) -> str:
        return self._name

    @staticmethod
    def _gen_system_message(
        system_role: Literal["developer", "system"], prompt: str, name: str
    ) -> EasyInputMessageParam:
        name_reminder = f"Your name will show up in messages as: {name}"
        full_prompt = f"{prompt}\n\n{name_reminder}"
        return EasyInputMessageParam(role=system_role, content=full_prompt)

    def gen_messages(self, _messages: Sequence[ChatMessage]) -> ResponseInputParam:
        msgs: list[ResponseInputItemParam] = [self.system_message]
        for msg in _messages:
            converted = self._convert_message(msg)
            msgs.append(converted)
        return msgs

    def _convert_message(self, msg: ChatMessage) -> EasyInputMessageParam:
        msg_author: str = msg.author
        role: Literal["assistant", "user", "system", "developer"] = "assistant"
        match msg.message_type:
            case MessageType.SPEECH:
                role = "assistant"
            case MessageType.NARRATION:
                role = "user"
            case MessageType.SYSTEM:
                role = self.system_role
            case MessageType.SUMMARY:
                role = "assistant"
                if msg_author == "DM" or msg_author == "GM":
                    role = "user"
        output = EasyInputMessageParam(
            role=role, content=f"{msg_author}: {msg.content}"
        )
        return output

    @override
    def respond(self, messages: Sequence[ChatMessage]) -> ChatMessage:

        input: ResponseInputParam | str | Omit = self.gen_messages(messages)
        response: Response = self.openai.responses.create(
            model=self.model,
            input=input,
            max_output_tokens=self.max_tokens,
            reasoning=self.reasoning,
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
