import logging
import threading
import time
from pathlib import Path
from typing import Callable, override

import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]

from rpg_player.domain.audio_recorder import AudioRecorder

log = logging.getLogger(__name__)


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
        self._current_path: Path | None = None

    @override
    async def start_recording(self, path: Path):
        if self.is_recording:
            log.warning(f"Already recording, ignoring start_recording({path})")
            return
        self._stop_flag.clear()
        start_time: float = time.time()
        self._current_path = path
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
            except Exception:
                log.exception("Recording error")

        self._thread = threading.Thread(target=record_loop, daemon=True)
        self._thread.start()

    @override
    async def stop_recording(self) -> None | Path:
        if not self.is_recording:
            log.warning("Stop called, but not currently recording")
            return None

        path = self._current_path
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self._current_path = None
        self._start_time = None
        log.info("Stopped recording")
        return path

    @override
    def register_progress_callback(self, callback: Callable[[float], None]):
        self._progress_callback = callback

    @property
    @override
    def is_recording(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    @override
    def current_recording(self) -> None | Path:
        return self._current_path
