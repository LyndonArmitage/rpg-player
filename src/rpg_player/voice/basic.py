import logging
from collections.abc import Iterable
from pathlib import Path
from typing import override

import pyttsx3  # pyright: ignore[reportMissingTypeStubs]

from rpg_player.domain.chat_message import ChatMessage, MessageType
from rpg_player.domain.voice_actor import OutLoudVoiceActor, VoiceActor, parse_names

log = logging.getLogger(__name__)


class BasicVoiceActor(VoiceActor, OutLoudVoiceActor):
    """
    A simple test VoiceActor that will use basic local TTS
    """

    def __init__(self, names: str | Iterable[str]):
        self.names: frozenset[str] = frozenset(parse_names(names))
        self.engine: pyttsx3.Engine = (
            pyttsx3.init()  # pyright: ignore[reportUnknownMemberType]
        )

    @property
    @override
    def speaker_names(self) -> frozenset[str]:
        return self.names

    @override
    def should_speak(self, msg: ChatMessage) -> bool:
        return (
            msg.message_type == MessageType.SPEECH
            and msg.author.casefold() in self.names
        )

    @override
    def synthesize(self, msg: ChatMessage, output_dir: Path) -> Path:
        log.debug(f"Speaking message {msg.msg_id} with local TTS")
        path = output_dir / "temp_speech.wav"
        text = msg.content.strip()
        self.engine.save_to_file(text, str(path))
        self.engine.runAndWait()
        return path

    @override
    def speak_message_out_loud(self, msg: ChatMessage) -> None:
        text = msg.content.strip()
        _ = self.engine.say(text)
        self.engine.runAndWait()
