import logging
from pathlib import Path
from typing import Iterable, Set, Union

import pyttsx3

from chat_message import ChatMessage, MessageType
from voice_actor import VoiceActor

log = logging.getLogger(__name__)


class BasicVoiceActor(VoiceActor):
    """
    A simple test VoiceActor that will use basic local TTS
    """

    def __init__(self, names: Union[str, Iterable[str]]):
        self.names = VoiceActor.parse_names(names)
        self.engine = pyttsx3.init()

    @property
    def speaker_names(self) -> Set[str]:
        return self.names

    def should_speak_message(self, message: ChatMessage) -> bool:
        return (
            message.type == MessageType.SPEECH
            and message.author.casefold() in self.names
        )

    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(f"Speaking message {message.msg_id} with local TTS")
        path = folder_path / "temp_speech.wav"
        text = message.content.strip()
        self.engine.save_to_file(text, str(path))
        self.engine.runAndWait()
        return path

    @property
    def can_speak_out_loud(self) -> bool:
        return True

    def speak_message_out_load(self, message: ChatMessage) -> None:
        text = message.content.strip()
        self.engine.say(text)
        self.engine.runAndWait()
