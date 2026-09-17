from pathlib import Path
from typing import Callable, Protocol


class AudioRecorder(Protocol):
    """
    Basic interface for recording audio.

    This assumes that only a single recording can be done at a time.
    """

    async def start_recording(self, path: Path) -> None:
        """Begin recording of audio to a given path"""
        ...

    async def stop_recording(self) -> None | Path:
        """
        Stop the current recording and returns the path to it.

        Returns None if no recording was being done.
        """
        ...

    @property
    def current_recording(self) -> None | Path:
        """
        returns the path for the current recording or None if no recording is
        happening
        """
        ...

    @property
    def is_recording(self) -> bool:
        """Returns true if we are currently recording"""
        ...

    def register_progress_callback(self, callback: Callable[[float], None]) -> None:
        """
        Registers a callback for reporting the elapsed recording time.

        The callable will be given this as a float in seconds.
        """
        ...
