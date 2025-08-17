from abc import ABC, abstractmethod
from typing import List, override

from openai import OpenAI

from chat_message import ChatMessage, ChatMessages


class Agent(ABC):
    """
    The base class for an AI Agent.

    AI Agents are fed the current messages and generate a response to them.
    """

    @abstractmethod
    def respond(self, messages: ChatMessages) -> ChatMessage:
        """
        Given the current state, and messages, respond.

        Will return a message that should be then processed and appended to the
        list of messages
        """
        raise NotImplementedError


class OpenAIAgent(Agent):
    """
    An AI Agent built using the OpenAI API.

    You will need to provide the client, the model, a name for the agent and a
    system prompt.
    """

    def __init__(self, openai: OpenAI, model: str, name: str, system_prompt: str):
        self.openai: OpenAI = openai
        self.model: str = model
        self.name: str = name
        self.system_prompt: str = system_prompt
        self.system_message: dict = OpenAIAgent._gen_system_message(system_prompt)

    @staticmethod
    def _gen_system_message(prompt: str) -> dict:
        return {"role": "developer", "content": prompt}

    @override
    def respond(self, messages: ChatMessages) -> ChatMessage:
        request_msgs: List[dict] = [self.system_message]
        request_msgs.extend(messages.as_openai)
        response = self.openai.responses.create(model=self.model, input=request_msgs)
        output_text = response.output_text
        return ChatMessage.speech(self.name, output_text)
