import logging
import tempfile
from pathlib import Path

from rpg_player.domain.chat_message import ChatMessage
from rpg_player.domain.voice_actor import OutLoudVoiceActor, VoiceActor

log = logging.getLogger(__name__)


class VoiceActorManager:
    """
    The VoiceActorManager holds all the VoiceActor instances and passes
    messages to them.
    """

    def __init__(self):
        self.actors: set[VoiceActor] = set()
        self._tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(
            prefix="rpg-voices"
        )
        self._tmp_path: Path = Path(self._tmp.name)

    def cleanup(self):
        """
        Will cleanup the temporary directory
        """
        self._tmp.cleanup()

    def register_actor(self, actor: VoiceActor):
        """
        Register a VoiceActor.

        The VoiceActor is responsible for deciding if a message is one it needs
        to speak and responsible for speaking.
        """
        if actor not in self.actors:
            log.debug(f"Registering actor: {actor}")
            self.actors.add(actor)

    def deregister_actor(self, actor: VoiceActor):
        """
        Deregister a VoiceActor if it is present.
        """
        if actor in self.actors:
            self.actors.remove(actor)

    def process_message(self, message: ChatMessage) -> tuple[bool, list[Path]]:
        """
        Given a message, process it, passing it to VoiceActor instances if
        needed.

        Will return a tuple of a boolean and list of file paths for the
        voiced lines. The first boolean from the tuple indicates if any Voice
        Actor spoke (be it writing to a file or out loud).

        The list of files should normally be a single file, but multiple files
        may be written, either by differnt voice actors or the same voice actor.

        If voice actors can speak out loud, they will not return a file and
        will instead block this function while they speak.
        """
        log.debug(f"Processing message: {message.msg_id}")
        paths: list[Path] = []
        spoke: bool = False
        for actor in self.actors:
            if actor.should_speak(message):
                if isinstance(actor, OutLoudVoiceActor):
                    actor.speak_message_out_loud(message)
                    spoke = True
                else:
                    path = actor.synthesize(message, self._tmp_path)
                    if path:
                        paths.append(path)
                        spoke = True
        return (spoke, paths)
