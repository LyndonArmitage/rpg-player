from pathlib import Path
from typing import Callable, Protocol


class AudioPlayer(Protocol):
    """
    The basic Audio Player interface.

    This only supports playing audio from a file and stopping the currently
    playing audio.
    """

    def play_file(self, path: Path) -> bool:
        """
        Play a given audio file, will return false if it was unable to be
        played due to being active.
        """
        ...

    def stop_audio(self) -> None:
        """Stop the currently playing audio file, if any."""
        ...

    @property
    def is_playing(self) -> bool: ...


class CallbackAudioPlayer(AudioPlayer, Protocol):
    """
    A more advanced Audio Player interface that supports callbacks for the
    progress of playing an audio file and finishing it.

    Useful if you want to block an interface.
    """

    def register_progress_callback(self, callback: Callable[[float, float], None]):
        """
        Register a progress callback.

        This callback is given the current time being played as well as the
        total duration. Both are in seconds as floating point numbers.
        """
        ...

    def register_finished_callback(self, callback: Callable[[Path], None]):
        """
        Registers a finished callback.

        This callback is given the path to the file that was played.
        """
        ...
