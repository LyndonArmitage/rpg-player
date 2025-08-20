from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union, override

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
        model: str = "gpt-5",
        temperature: float = 0.4,
        max_tokens: int = 300,
        prefix_path: Optional[Union[Path, str]] = None,
        suffix_path: Optional[Union[Path, str]] = None,
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
        system_prompt: str = path.read_text()

        if prefix_path:
            if not isinstance(prefix_path, Path):
                prefix_path: Path = Path(prefix_path)
            prefix_prompt: str = prefix_path.read_text()
            system_prompt = prefix_prompt + "\n" + system_prompt

        if suffix_path:
            if not isinstance(suffix_path, Path):
                suffix_path: Path = Path(suffix_path)
            suffix_prompt: str = suffix_path.read_text()
            system_prompt = system_prompt + "\n" + suffix_prompt

        return OpenAIAgent(openai, name, system_prompt, model, temperature, max_tokens)

    def __init__(
        self,
        openai: OpenAI,
        name: str,
        system_prompt: str,
        model: str = "gpt-5",
        temperature: float = 0.4,
        max_tokens: int = 300,
    ):
        self.openai: OpenAI = openai
        self._name: str = name
        self.system_prompt: str = system_prompt
        self.model: str = model
        self.temperature: float = temperature
        self.max_tokens: int = max_tokens
        self.system_message: dict = OpenAIAgent._gen_system_message(system_prompt, name)

    @property
    @override
    def name(self) -> str:
        return self._name

    @staticmethod
    def _gen_system_message(prompt: str, name: str) -> dict:
        name_reminder = f"Your name will show up in messages as: {name}"
        return {"role": "developer", "content": f"{prompt}\n\n{name_reminder}"}

    @override
    def respond(self, messages: ChatMessages) -> ChatMessage:
        request_msgs: List[dict] = [self.system_message]
        request_msgs.extend(messages.as_openai)
        response = self.openai.responses.create(
            model=self.model,
            input=request_msgs,
            temperature=self.temperature,
            tool_choice="none",
            stream=False,
            max_output_tokens=self.max_tokens,
        )
        output_text = response.output_text
        return ChatMessage.speech(self._name, output_text)
