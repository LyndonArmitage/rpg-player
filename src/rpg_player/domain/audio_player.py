from pathlib import Path
from typing import Callable, Protocol


class AudioPlayer(Protocol):
    """
    The basic Audio Player interface.

    This only supports playing audio from a file and stopping the currently
    playing audio.
    """

    def play_file(self, path: Path) -> None: ...

    def stop_audio(self) -> None: ...


class CallbackAudioPlayer(AudioPlayer, Protocol):
    """
    A more advanced Audio Player interface that supports callbacks for the
    progress of playing an audio file and finishing it.

    Useful if you want to block an interface.

    The callables are given a current time position in seconds and a total
    duration in seconds as floating point numbers.

    The finished callback should be called when audio is stopped naturally or
    intentionally.
    """

    def register_progress_callback(self, callback: Callable[[float, float], None]): ...

    def register_finished_callback(self, callback: Callable[[float, float], None]): ...
