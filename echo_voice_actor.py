import tempfile
import logging
from pathlib import Path
from typing import Iterable, Set, Union

from voice_actor import VoiceActor
from chat_message import ChatMessage, MessageType

log = logging.getLogger(__name__)


class EchoVoiceActor(VoiceActor):
    """
    A simple test VoiceActor that will echo out all messages to the log and
    save a text copy of them to a temporay file.
    """

    def __init__(self, names: Union[str, Iterable[str]]):
        self.names = VoiceActor.parse_names(names)

    @property
    def speaker_names(self) -> Set[str]:
        return self.names

    def should_speak_message(self, message: ChatMessage) -> bool:
        # Will speak all speech messages
        return message.type == MessageType.SPEECH

    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(f"Speaking message {message.msg_id} with Echo")
        path = None
        with tempfile.NamedTemporaryFile(
            dir=folder_path, suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as f:
            log.info(f"{message.author}: {message.content}")
            f.write(message.content)
            path = Path(f.name)
        return path

    @property
    def can_speak_out_loud(self) -> bool:
        return False

    def speak_message_out_load(self, message: ChatMessage) -> None:
        raise NotImplementedError
