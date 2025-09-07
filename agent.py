import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union, override

from jinja2 import Environment, Template
from openai import OpenAI

from chat_message import ChatMessage, ChatMessages


class Agent(ABC):
    """
    The base class for an AI Agent.

    AI Agents are fed the current messages and generate a response to them.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        The name of the agent
        """
        raise NotImplementedError

    @abstractmethod
    def respond(self, messages: ChatMessages) -> ChatMessage:
        """
        Given the current state, and messages, respond.

        Will return a message that should be then processed and appended to the
        list of messages
        """
        raise NotImplementedError


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
    def respond(self, messages: ChatMessages) -> ChatMessage:
        return ChatMessage.speech(self._name, self.message)


class OpenAIAgent(Agent):
    """
    An AI Agent built using the OpenAI API.

    You will need to provide the client, the model, a name for the agent and a
    system prompt.
    """

    @staticmethod
    def load_prompt(
        name: str,
        path: Union[Path, str],
        openai: OpenAI,
        model: str = "gpt-4.1",
        max_tokens: int = 3000,
        prefix_path: Optional[Union[Path, str]] = None,
        suffix_path: Optional[Union[Path, str]] = None,
        extra_kwargs: Optional[dict] = None,
    ) -> "OpenAIAgent":
        """
        Create an agent, loading the prompt from a file.

        Optionally can load a prefix prompt and suffix prompt which will be
        added before and after the main prompt respectively.
        """
        if not isinstance(path, Path):
            path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")

        # Create jinja environment and template variables to use
        env = Environment()
        template_vars: dict = {
            "name": name,
            "model": model,
        }

        system_prompt_template: Template = env.from_string(path.read_text("utf-8"))
        system_prompt: str = system_prompt_template.render(**template_vars)

        if prefix_path:
            if not isinstance(prefix_path, Path):
                prefix_path: Path = Path(prefix_path)
            prefix_template: Template = env.from_string(prefix_path.read_text("utf-8"))
            prefix_prompt: str = prefix_template.render(**template_vars)
            system_prompt = prefix_prompt + "\n" + system_prompt

        if suffix_path:
            if not isinstance(suffix_path, Path):
                suffix_path: Path = Path(suffix_path)
            suffix_template: Template = env.from_string(suffix_path.read_text("utf-8"))
            suffix_prompt: str = suffix_template.render(**template_vars)
            system_prompt = system_prompt + "\n" + suffix_prompt

        return OpenAIAgent(
            openai, name, system_prompt, model, max_tokens, extra_kwargs=extra_kwargs
        )

    def __init__(
        self,
        openai: OpenAI,
        name: str,
        system_prompt: str,
        model: str = "gpt-4.1",
        max_tokens: int = 3000,
        extra_kwargs: Optional[dict] = None,
    ):
        self.openai: OpenAI = openai
        self._name: str = name
        self.system_prompt: str = system_prompt
        self.model: str = model
        self.max_tokens: int = max_tokens
        self.system_message: str = OpenAIAgent._gen_system_message(system_prompt, name)
        self.log = logging.getLogger(f"OpenAIAgent-{name}")

        reserved_keys = {
            "model",
            "input",
            "instructions",
            "tool_choice",
            "stream",
            "max_output_tokens",
        }
        extra_kwargs = extra_kwargs or {}
        intersection = reserved_keys & extra_kwargs.keys()
        if intersection:
            raise ValueError(
                (
                    "extra_kwargs contains reserved keyword(s) "
                    f"that will be overwritten: {sorted(intersection)}"
                )
            )
        # Consolidate static params for responses.create
        self.response_kwargs = {
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
    def respond(self, messages: ChatMessages) -> ChatMessage:
        request_msgs: List[dict] = messages.as_openai
        response = self.openai.responses.create(
            input=request_msgs,
            **self.response_kwargs,
        )
        output_text = OpenAIAgent._extract_text(response)
        if not output_text:
            self.log.warning(
                "No assistant message in response; got: %s", response.output
            )
        return ChatMessage.speech(self._name, output_text)

    def _extract_text(response) -> str:
        # Prefer walking the structured output
        out = getattr(response, "output", None) or []
        collected: list[str] = []

        for item in out:
            # GPT-4/GPT-5 both use 'message' items for assistant replies
            if getattr(item, "type", None) == "message":
                # item.content is a list of blocks; we want output_text blocks
                for block in getattr(item, "content", []) or []:
                    if getattr(block, "type", None) == "output_text":
                        txt = getattr(block, "text", "") or ""
                        if txt:
                            collected.append(txt)

        if collected:
            return "\n".join(collected).strip()

        # Fallback for SDK helpers that sometimes populate this
        return (getattr(response, "output_text", "") or "").strip()
