import logging
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, override

import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]

log = logging.getLogger(__name__)


class AudioRecorder(ABC):
    """
    The basic interface for an audio recorder.

    The implementors should provide at least asynchronous recording control:
    - `start_recording` to begin capturing audio to a file.
    - `stop_recording` to finish and save.
    """

    @abstractmethod
    async def start_recording(self, path: Path) -> None:
        """
        Begins recording audio asynchronously to the specified path.
        """
        raise NotImplementedError

    @abstractmethod
    async def stop_recording(self) -> None:
        """
        Stops the ongoing recording.
        """
        raise NotImplementedError

    @abstractmethod
    def register_progress_callback(self, callback: Callable[[float], None]) -> None:
        """
        Optionally registers a callback reporting the elapsed recording time.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_recording(self) -> bool:
        """
        Indicates if recording is currently active.
        """
        raise NotImplementedError


class SoundDeviceRecorder(AudioRecorder):
    """
    Implementation of AudioRecorder using sounddevice and soundfile.
    Non-blocking, supports progress callback.
    """

    def __init__(
        self, samplerate: int = 44100, channels: int = 1, subtype: str = "PCM_16"
    ):
        self._thread: threading.Thread | None = None
        self._stop_flag: threading.Event = threading.Event()
        self._progress_callback: Callable[[float], None] | None = None
        self._samplerate: int = samplerate
        self._channels: int = channels
        self._subtype: str = subtype
        self._start_time: float | None = None

    @override
    async def start_recording(self, path: Path):
        if self.is_recording:
            log.warning(f"Already recording, ignoring start_recording({path})")
            return
        self._stop_flag.clear()
        start_time: float = time.time()
        self._start_time = start_time

        def record_loop():
            try:
                with sf.SoundFile(
                    path,
                    mode="w",
                    samplerate=self._samplerate,
                    channels=self._channels,
                    subtype=self._subtype,
                ) as file:
                    with sd.InputStream(
                        samplerate=self._samplerate,
                        channels=self._channels,
                        dtype="int16",
                    ) as stream:
                        while not self._stop_flag.is_set():
                            data, _ = (
                                stream.read(  # pyright: ignore[reportUnknownMemberType]
                                    1024
                                )
                            )
                            file.write(data)
                            if self._progress_callback:
                                elapsed: float = time.time() - start_time
                                # Call callback with elapsed seconds
                                try:
                                    self._progress_callback(elapsed)
                                except Exception:
                                    log.exception("Progress callback failed")
            except Exception as e:
                log.error(f"Recording error: {e}")

        self._thread = threading.Thread(target=record_loop, daemon=True)
        self._thread.start()

    @override
    async def stop_recording(self):
        if self.is_recording:
            self._stop_flag.set()
            if self._thread:
                self._thread.join(timeout=5)
            self._thread = None
            log.info("Stopped recording")
        else:
            log.warning("Stop called, but not currently recording")

    @override
    def register_progress_callback(self, callback: Callable[[float], None]):
        self._progress_callback = callback

    @property
    @override
    def is_recording(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
