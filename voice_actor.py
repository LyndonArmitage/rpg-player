import logging
from abc import ABC, abstractmethod
from typing import List, override

from chat_message import ChatMessage, MessageType

log = logging.getLogger(__name__)


class VoiceActor(ABC):
    """
    A VoiceActor is a class that can speak messages.
    """

    @abstractmethod
    def speak_message(self, message: ChatMessage):
        """
        Speak the given message
        """

        raise NotImplementedError

    @abstractmethod
    def should_speak_message(self, message: ChatMessage) -> bool:
        """
        Return true if this voice actor should speak the message
        """
        raise NotImplementedError


class EchoVoiceActor(VoiceActor):
    """
    A simple test VoiceActor that will echo out all messages to the log
    """

    @override
    def should_speak_message(self, message: ChatMessage) -> bool:
        # Will speak all speech messages
        return message.type == MessageType.SPEECH

    @override
    def speak_message(self, message: ChatMessage):
        log.info(f"{message.author}: {message.content}")


class VoiceActorManager:
    """
    The VoiceActorManager holds all the VoiceActor instances and passes
    messages to them.
    """

    def __init__(self):
        self.actors: List[VoiceActor] = []

    def register_actor(self, actor: VoiceActor):
        """
        Register a VoiceActor.

        The VoiceActor is responsible for deciding if a message is one it needs
        to speak and responsible for speaking.
        """
        if actor not in self.actors:
            log.debug(f"Registering actor: {actor}")
            self.actors.append(actor)

    def deregister_actor(self, actor: VoiceActor):
        """
        Deregister a VoiceActor if it is present.
        """
        if actor in self.actors:
            self.actors.remove(actor)

    def process_message(self, message: ChatMessage):
        """
        Given a message, process it, passing it to VoiceActor instances if
        needed.
        """
        log.debug(f"Processing message: {message.id}")
        for actor in self.actors:
            if actor.should_speak_message(message):
                actor.speak_message(message)
