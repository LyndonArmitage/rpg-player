import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

from agent import Agent
from audio_player import SoundDevicePlayer
from chat_message import ChatMessage, ChatMessages
from voice_actor import VoiceActorManager

log = logging.getLogger(__name__)


class StateMachine:
    """
    The main application state machine
    """

    @staticmethod
    def _load_messages_file(file: Path, container: ChatMessages):
        log.info(f"Loading messages file: {file}")
        # Load messages file
        count = 0
        with open(file, "r") as f:
            for line in f:
                entry = json.loads(line)
                message = ChatMessage.from_dict(entry)
                container.append(message)
                count += 1
        log.info(f"Read {count} messages")

    @staticmethod
    def _create_empty_messages_file(file: Path):
        log.info(f"Creating empty messages file: {file}")
        # Create folder for messages_file
        file.parent.mkdir(parents=True, exist_ok=True)
        # Create messages file
        file.touch()

    def __init__(
        self,
        agents: List[Agent],
        voice_actors: VoiceActorManager,
        message_listener: Optional[Callable[[ChatMessage], None]] = None,
        messages_file: Optional[Path] = None,
        delete_audio: bool = True,
    ):
        self.messages: ChatMessages = ChatMessages()
        self.agents: List[Agent] = agents
        self.voice_actors: VoiceActorManager = voice_actors
        self.player: SoundDevicePlayer = SoundDevicePlayer()
        if delete_audio:

            def delete_path(path: Path):
                log.debug(f"Deleting {path}")
                path.unlink(missing_ok=True)

            self.player.register_finished_callback(delete_path)

        self.message_listener: Optional[Callable[[ChatMessage], None]] = (
            message_listener
        )

        # Loading and restoring state
        self.messages_file: Optional[Path] = None
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
                f.write(json.dumps(message.as_dict()))
                f.write("\n")
        if self.message_listener:
            self.message_listener(message)

    @property
    def agent_names(self) -> List[str]:
        return [a.name for a in self.agents]

    def get_last_message(
        self, exclude_authors: Optional[List[str]] = None
    ) -> Optional[ChatMessage]:
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
        # Add the message to our container
        self.add_message(response)
        return response

    def play_message(self, message: ChatMessage):
        voice_paths: List[Path] = self.voice_actors.process_message(message)
        if voice_paths:
            voice_count: int = len(voice_paths)
            if voice_count > 1:
                log.warning(f"Multiple voice files, will play first: {voice_paths}")
            self.play_audio(voice_paths[0])
        else:
            log.warning(f"No actor for message from {message.author} {message.msg_id}")

    def play_audio(self, path: Path):
        log.debug(f"Playing audio: {path}")
        if self.player.is_playing or self.player.is_paused:
            self.player.stop_audio()
        self.player.play_file(path)

    def stop_audio(self):
        self.player.stop_audio()
