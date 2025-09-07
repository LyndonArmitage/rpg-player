import logging
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Set, Union

from chat_message import ChatMessage

log = logging.getLogger(__name__)


class VoiceActor(ABC):
    """
    A VoiceActor is a class that can speak messages.
    """

    @staticmethod
    def parse_names(names: Union[str, Iterable[str]]) -> Set[str]:
        """
        Normalize names into a set of casefolded strings.

        names can be a single string or some kind of Iterable
        """
        # Normalize names into a set of casefolded strings
        if isinstance(names, str):
            norm_names: Set[str] = {names.casefold()}
        else:
            # Ensure it's an iterable of strings
            try:
                norm_names = {n.casefold() for n in names}  # type: ignore[arg-type]
            except TypeError:
                raise TypeError("names must be a string or an iterable of strings")
            if not all(isinstance(n, str) for n in names):  # type: ignore[iterable-issue]
                raise TypeError("all elements of 'names' must be strings")
        return norm_names

    @abstractmethod
    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        """
        Speak the given message, saving it to a file in the given path and
        returning the path to the file
        """

        raise NotImplementedError

    @abstractmethod
    def should_speak_message(self, message: ChatMessage) -> bool:
        """
        Return true if this voice actor should speak the message
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def speaker_names(self) -> Set[str]:
        """
        The speaker names this voice actor will work for
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def can_speak_out_loud(self) -> bool:
        """
        True if this voice actor supports speaking out loud
        """
        return False

    @abstractmethod
    def speak_message_out_load(self, message: ChatMessage) -> None:
        """
        Speak the given message out loud. This will not save the message to a
        file but instead speak the message through the audio output device as
        soon as possible.

        Not all voice actors will be able to do this so you should check if it
        is possible first.
        """
        raise NotImplementedError


class VoiceActorManager:
    """
    The VoiceActorManager holds all the VoiceActor instances and passes
    messages to them.
    """

    def __init__(self):
        self.actors: Set[VoiceActor] = set()
        self._tmp: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory(
            prefix="rpg-voices"
        )
        self._tmp_path = Path(self._tmp.name)

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

    def process_message(self, message: ChatMessage) -> (bool, List[Path]):
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
        paths: List[Path] = []
        spoke: bool = False
        for actor in self.actors:
            if actor.should_speak_message(message):
                if actor.can_speak_out_loud:
                    actor.speak_message_out_load(message)
                    spoke = True
                else:
                    path = actor.speak_message(message, self._tmp_path)
                    if path:
                        paths.append(path)
                        spoke = True
        return (spoke, paths)
