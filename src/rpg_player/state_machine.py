import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from rpg_player.audio.sounddevice import SoundDevicePlayer
from rpg_player.domain.agent import Agent
from rpg_player.domain.chat_message import (
    ChatMessage,
    ChatMessages,
    load_messages_from_file,
)

from .message_transformer import ChatMessageTransformer
from .voice_actor import VoiceActorManager

log = logging.getLogger(__name__)


class StateMachine:
    """
    The main application state machine
    """

    @staticmethod
    def _load_messages_file(file: Path, container: ChatMessages):
        log.info(f"Loading messages file: {file}")
        loaded_msgs: list[ChatMessage] = load_messages_from_file(file)
        # Load messages file
        count = len(loaded_msgs)
        log.info(f"Read {count} messages")
        container.extend(loaded_msgs)

    @staticmethod
    def _create_empty_messages_file(file: Path):
        log.info(f"Creating empty messages file: {file}")
        # Create folder for messages_file
        file.parent.mkdir(parents=True, exist_ok=True)
        # Create messages file
        file.touch()

    def __init__(
        self,
        agents: list[Agent],
        voice_actors: VoiceActorManager,
        message_listener: Callable[[ChatMessage], None] | None = None,
        messages_file: Path | None = None,
        delete_audio: bool = True,
        system_role: str = "developer",
        message_transformer: ChatMessageTransformer | None = None,
    ):
        self.messages: ChatMessages = ChatMessages()
        self.agents: list[Agent] = agents
        self.voice_actors: VoiceActorManager = voice_actors
        self.player: SoundDevicePlayer = SoundDevicePlayer()
        self.message_transformer: ChatMessageTransformer | None = message_transformer
        if delete_audio:

            def delete_path(path: Path):
                log.debug(f"Deleting {path}")
                path.unlink(missing_ok=True)

            self.player.register_finished_callback(delete_path)

        self.message_listener: Callable[[ChatMessage], None] | None = message_listener

        # Loading and restoring state
        self.messages_file: Path | None = None
        if messages_file:
            self.messages_file = messages_file
            if messages_file.exists():
                # Load previous files
                StateMachine._load_messages_file(messages_file, self.messages)
            else:
                StateMachine._create_empty_messages_file(messages_file)
        else:
            log.warning("Not using messages file")

    def add_message(self, message: ChatMessage):
        log.debug(f"Adding message: {message.msg_id}")
        self.messages.append(message)
        if self.messages_file:
            # Append to messages file
            with self.messages_file.open("a", encoding="utf-8") as f:
                _ = f.write(json.dumps(asdict(message)))
                _ = f.write("\n")
        if self.message_listener:
            self.message_listener(message)

    @property
    def agent_names(self) -> list[str]:
        return [a.name for a in self.agents]

    def get_last_message(
        self, exclude_authors: list[str] | None = None
    ) -> ChatMessage | None:
        """
        Return the last chat message, optionally excluding the list of authors.
        """
        for msg in reversed(self.messages.messages):
            if exclude_authors and msg.author in exclude_authors:
                continue
            return msg
        return None

    def agent_respond(self, index: int) -> ChatMessage:
        """
        Given an agent index, asks the agent to respond
        """
        length = len(self.agents)
        if index >= length:
            raise IndexError(
                f"{index} is out of bounds for agents list of length {length}"
            )
        agent: Agent = self.agents[index]
        response: ChatMessage = agent.respond(self.messages)
        # Transformer an agent response if needed
        if self.message_transformer:
            response = self.message_transformer.transform(response)
        # Add the message to our container
        self.add_message(response)
        return response

    def play_message(self, message: ChatMessage):
        spoke, voice_paths = self.voice_actors.process_message(message)
        if voice_paths:
            voice_count: int = len(voice_paths)
            if voice_count > 1:
                log.warning(f"Multiple voice files, will play first: {voice_paths}")
            self.play_audio(voice_paths[0])
        elif not spoke:
            log.warning(f"No actor for message from {message.author} {message.msg_id}")

    def play_audio(self, path: Path):
        log.debug(f"Playing audio: {path}")
        if self.player.is_playing:
            self.player.stop_audio()
        _ = self.player.play_file(path)

    def stop_audio(self):
        self.player.stop_audio()
