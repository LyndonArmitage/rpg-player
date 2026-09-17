import logging
import queue
import threading
import time
from pathlib import Path
from typing import Callable, cast, override

import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]

from rpg_player.domain.audio_player import CallbackAudioPlayer
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


class SoundDevicePlayer(CallbackAudioPlayer):
    """Play sound files asynchronously using a ``sounddevice`` callback.

    ``RawOutputStream`` is used deliberately here.  ``SoundFile.buffer_read``
    returns bytes, so audio can be passed from the file to the output device
    without converting it to a NumPy array (or loading the whole file into
    memory).
    """

    def __init__(self, blocksize: int = 1024, buffersize: int = 8):
        if blocksize <= 0:
            raise ValueError("blocksize must be greater than zero")
        if buffersize <= 0:
            raise ValueError("buffersize must be greater than zero")

        self._blocksize: int = blocksize
        self._buffersize: int = buffersize
        self._thread: threading.Thread | None = None
        self._stop_flag: threading.Event = threading.Event()
        self._progress_callback: Callable[[float, float], None] | None = None
        self._finished_callback: Callable[[Path], None] | None = None
        self._lock: threading.Lock = threading.Lock()
        self._current_path: Path | None = None
        self._duration: float = 0.0
        self._frames_played: int = 0
        self._samplerate: int = 0

    @override
    def play_file(self, path: Path) -> bool:
        with self._lock:
            if self.is_playing:
                log.warning("Tried to play %s while another file is playing", path)
                return False

            try:
                info = sf.info(path)
            except Exception:
                log.exception("Unable to read audio file %s", path)
                return False

            self._stop_flag.clear()
            self._current_path = path
            self._duration = info.frames / info.samplerate if info.samplerate else 0.0
            self._frames_played = 0
            self._thread = threading.Thread(
                target=self._play_loop, args=(path,), daemon=True
            )
            thread = self._thread

        self._report_progress(0.0)
        thread.start()
        return True

    def _report_progress(self, current: float) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(current, self._duration)
        except Exception:
            log.exception("Progress callback failed")

    def _play_loop(self, path: Path) -> None:
        chunks: queue.Queue[bytes] = queue.Queue(maxsize=self._buffersize)

        def callback(
            outdata: bytearray, frames: int, _time: object, status: object
        ) -> None:
            if status:
                log.warning("Audio output status: %s", status)
            if self._stop_flag.is_set():
                raise sd.CallbackAbort

            try:
                data = chunks.get_nowait()
            except queue.Empty as error:
                log.error("Audio buffer underrun while playing %s", path)
                self._stop_flag.set()
                raise sd.CallbackAbort from error

            # RawOutputStream exposes a byte buffer.  A short final chunk must
            # be padded because PortAudio always asks for a full block.
            expected_bytes = len(outdata)
            if len(data) < expected_bytes:
                outdata[: len(data)] = data
                outdata[len(data) :] = b"\x00" * (expected_bytes - len(data))
                self._frames_played += frames
                self._report_progress(
                    min(
                        self._frames_played / self._samplerate,
                        self._duration,
                    )
                )
                self._stop_flag.set()
                raise sd.CallbackStop

            outdata[:] = data[:expected_bytes]
            self._frames_played += frames
            self._report_progress(
                min(
                    self._frames_played / self._samplerate,
                    self._duration,
                )
            )

        try:
            with sf.SoundFile(path) as file:
                # Fill the queue before starting PortAudio so the callback does
                # not immediately underrun on slower disks.
                while not self._stop_flag.is_set() and not chunks.full():
                    data = file.buffer_read(self._blocksize, dtype="float32")
                    if not data:
                        break
                    chunks.put_nowait(bytes(data))

                samplerate: int = cast(int, file.samplerate)
                channels: int = cast(int, file.channels)
                self._samplerate = samplerate
                with sd.RawOutputStream(
                    samplerate=samplerate,
                    blocksize=self._blocksize,
                    channels=channels,
                    dtype="float32",
                    callback=callback,
                ):
                    while not self._stop_flag.is_set():
                        try:
                            data = file.buffer_read(self._blocksize, dtype="float32")
                        except Exception:
                            log.exception("Error reading audio file %s", path)
                            break
                        if not data:
                            break
                        try:
                            chunks.put(bytes(data), timeout=0.1)
                        except queue.Full:
                            continue
                    # An empty chunk marks EOF.  It is consumed after all
                    # audio chunks and lets the callback stop the stream.
                    if not self._stop_flag.is_set():
                        while not self._stop_flag.is_set():
                            try:
                                chunks.put(b"", timeout=0.1)
                                break
                            except queue.Full:
                                continue
        except Exception:
            if not self._stop_flag.is_set():
                log.exception("Playback error for %s", path)
        finally:
            self._stop_flag.clear()
            self._current_path = None
            self._thread = None
            if self._finished_callback:
                try:
                    self._finished_callback(path)
                except Exception:
                    log.exception("Finished callback failed")

    @override
    def stop_audio(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        self._stop_flag.set()
        if thread is not threading.current_thread():
            thread.join(timeout=5)

    @property
    @override
    def is_playing(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @override
    def register_progress_callback(
        self, callback: Callable[[float, float], None]
    ) -> None:
        self._progress_callback = callback

    @override
    def register_finished_callback(self, callback: Callable[[Path], None]) -> None:
        self._finished_callback = callback
