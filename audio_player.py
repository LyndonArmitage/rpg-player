import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, override

import sounddevice as sd
import soundfile as sf

log = logging.getLogger(__name__)


class AudioPlayer(ABC):
    """
    The basic interface for an audio player.

    The implementors may not implement all features of this class but at lease
    `play_file` should be implemented.

    An ideal implementation should be non-blocking.
    """

    @abstractmethod
    def register_progress_callback(self, callback: Callable[[float, float], None]):
        """
        Registers a callback that the implementations should call during
        playback.

        The callback takes a current time position (as seconds) and the total
        duration (as seconds). Both are floating point numbers
        """
        raise NotImplementedError

    @abstractmethod
    def play_file(self, path: Path):
        raise NotImplementedError

    @abstractmethod
    def stop_audio(self):
        raise NotImplementedError

    @abstractmethod
    def pause(self):
        raise NotImplementedError

    @abstractmethod
    def resume(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def is_playing(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_paused(self) -> bool:
        raise NotImplementedError


class SoundDevicePlayer(AudioPlayer):
    """
    Implementation of AudioPlayer using `sounddevice` and `soundfile`.

    This implementation is non-blocking and supports pausing, resuming, and
    callbacks.
    """

    def __init__(self, blocksize: int = 1024):
        self._thread: Optional[threading.Thread] = None
        self._stop_flag: threading.Event = threading.Event()
        self._unpaused: threading.Event = threading.Event()
        self._blocksize: int = blocksize
        self._progress_callback: Optional[Callable[[float, float], None]] = None
        self._frames_played: int = 0
        self._samplerate: int = 0
        self._duration: float = 0.0
        # loop sets this when it observes paused
        self._pause_ack = threading.Event()

    @override
    def register_progress_callback(self, callback: Callable[[float, float], None]):
        self._progress_callback = callback

    @override
    def play_file(self, path: Path) -> bool:
        if self.is_playing:
            log.warning(f"Tried to play {path} when already playing")
            return False
        self._stop_flag.clear()
        self._unpaused.set()
        self._frames_played = 0
        info = sf.info(path)
        self._samplerate = info.samplerate
        self._duration = info.frames / info.samplerate
        if self._progress_callback:
            self._progress_callback(0.0, self._duration)
        self._thread = threading.Thread(
            target=self._play_loop, args=(path,), daemon=True
        )
        self._thread.start()
        return True

    def _play_loop(self, path: Path):
        try:
            with sf.SoundFile(path) as f:
                with sd.OutputStream(
                    samplerate=f.samplerate,
                    channels=f.channels,
                    latency="high",
                    dtype="float32",
                ) as stream:
                    self._samplerate = f.samplerate
                    for block in f.blocks(blocksize=self._blocksize, dtype="float32"):
                        if self._stop_flag.is_set():
                            # Stop playing
                            break
                        if not self._unpaused.is_set():
                            stream.stop()
                            self._pause_ack.set()

                            # Sleep efficiently until resume or stop
                            while not self._stop_flag.is_set():
                                if self._unpaused.wait(
                                    timeout=0.1
                                ):  # returns True if set (resumed)
                                    break

                            if self._stop_flag.is_set():
                                break
                            # Resume the stream and starts writing the same block
                            stream.start()

                        stream.write(block)
                        self._frames_played += len(block)
                        if self._progress_callback and self._samplerate > 0:
                            elapsed_sec: float = self._frames_played / self._samplerate
                            self._progress_callback(elapsed_sec, self._duration)
        except Exception as e:
            log.error(f"Playback error for {path}: {e}")
        finally:
            self._thread = None
            self._stop_flag.clear()
            log.info(f"Playback of {path} finished or stopped")

    @override
    def stop_audio(self):
        if self.is_playing:
            self._stop_flag.set()
            self._unpaused.set()
            self._thread.join()
            self._thread = None
            log.info("Stopped playback")
        else:
            log.warning("No audio to stop")

    @override
    def pause(self):
        self._pause_ack.clear()
        self._unpaused.clear()
        self._pause_ack.wait(timeout=0.5)
        log.info("Pausing playback")

    @override
    def resume(self):
        self._unpaused.set()
        log.info("Resuming playback")

    @property
    @override
    def is_playing(self) -> bool:
        return bool(
            self._thread and self._thread.is_alive() and self._unpaused.is_set()
        )

    @property
    @override
    def is_paused(self) -> bool:
        return bool(
            self._thread and self._thread.is_alive() and not self._unpaused.is_set()
        )
