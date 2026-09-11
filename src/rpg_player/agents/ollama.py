import logging
from collections.abc import Sequence
from typing import override

from ollama import ChatResponse, Client

from rpg_player.domain.agent import Agent
from rpg_player.domain.chat_message import ChatMessage


class OllamaAgent(Agent):
    """
    An AI Agent built using the Ollama API.

    You will need to provide the client, the model, a name for the agent and a
    system prompt.

    The client used can be the default one `ollama._client` if you don't need
    to configure it.
    """

    def __init__(
        self,
        client: Client,
        name: str,
        system_prompt: str,
        model: str,
        max_tokens: int = 4096,
    ):
        self.ollama: Client = client

        self._name: str = name
        self.model: str = model
        self.max_tokens: int = max_tokens
        self.log: logging.Logger = logging.getLogger(f"OllamaAgent-{name}")
        self._system_message: dict[str, str] = OllamaAgent._gen_system_message(
            system_prompt, name
        )

    @property
    @override
    def name(self) -> str:
        return self._name

    @staticmethod
    def _gen_system_message(prompt: str, name: str) -> dict[str, str]:
        name_reminder = f"Your name will show up in messages as: {name}"
        full_prompt = f"{prompt}\n\n{name_reminder}"
        return {"role": "system", "content": full_prompt}

    @override
    def respond(self, messages: Sequence[ChatMessage]) -> ChatMessage:
        all_messages: list[dict[str, str]] = [self._system_message]
        request_msgs: list[dict[str, str]] = []
        for raw_msg in messages:
            msg = raw_msg.as_openai_msg()
            # Only difference between OpenAI and Ollama is that OpenAI supports
            # "developer" in gpt-5 while Ollama still uses "system"
            if msg["role"] == "developer":
                new_msg = {"role": "system", "content": msg["content"]}
                all_messages.append(new_msg)
            else:
                all_messages.append(msg)
        all_messages.extend(request_msgs)

        # TODO: Handle this Ollama pyright ignore
        response: ChatResponse = (
            self.ollama.chat(  # pyright: ignore[reportUnknownMemberType]
                model=self.model, messages=all_messages, stream=False
            )
        )

        output_text = response.message.content
        if not output_text:
            self.log.warning(f"No assistant message in response; got: {response}")
            output_text = ""
        return ChatMessage.speech(self._name, output_text)
