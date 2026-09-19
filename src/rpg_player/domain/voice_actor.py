from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from rpg_player.domain.chat_message import ChatMessage


class VoiceActor(Protocol):
    """
    Protocol defining a voice actor.

    A voice actor is a class that can provide text-to-speech capabilities for
    a speaker or multiple speakers.

    A VoiceActor must be able to synthesize speech to a file.

    Additionally you may want to implement the OutLoudVoiceActor protocol.
    """

    @property
    def speaker_names(self) -> frozenset[str]:
        """The speaker names this voice actor is for"""
        ...

    def should_speak(self, msg: ChatMessage) -> bool:
        """Whether this voice actor should speak the given message"""
        ...

    def synthesize(self, msg: ChatMessage, output_dir: Path) -> Path:
        """
        Synthesize the speech in the message to the given folder, returning the
        path to the new file.
        """
        ...


@runtime_checkable
class OutLoudVoiceActor(Protocol):
    """
    Extended Voice Actor protocol that supports speaking out loud rather than
    offloading to a file.
    """

    def speak_message_out_loud(self, msg: ChatMessage) -> None:
        """Speak a message out load"""
        ...


def parse_names(names: str | Iterable[str]) -> set[str]:
    """
    Normalize names into a set of casefolded strings.

    names can be a single string or some kind of Iterable
    """
    # Normalize names into a set of casefolded strings
    if isinstance(names, str):
        norm_names: set[str] = {names.casefold()}
    else:
        # Ensure it's an iterable of strings
        try:
            norm_names = {n.casefold() for n in names}
        except TypeError as err:
            raise TypeError("names must be a string or an iterable of strings") from err
    return norm_names
