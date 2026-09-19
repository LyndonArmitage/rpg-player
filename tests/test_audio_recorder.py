from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import ClassVar

from _pytest.monkeypatch import MonkeyPatch

from rpg_player.audio import sounddevice
from rpg_player.audio.sounddevice import SoundDeviceRecorder


class FakeSoundFile:
    instances: ClassVar[list[FakeSoundFile]] = []

    def __init__(self, path: Path, **kwargs: object) -> None:
        self.path: Path = path
        self.options: dict[str, object] = kwargs
        self.writes: list[list[int]] = []
        self.closed: bool = False
        type(self).instances.append(self)

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def write(self, data: list[int]) -> None:
        self.writes.append(data)


class FakeInputStream:
    instances: ClassVar[list[FakeInputStream]] = []

    def __init__(self, **kwargs: object) -> None:
        self.options: dict[str, object] = kwargs
        self.read_started: threading.Event = threading.Event()
        self.closed: bool = False
        type(self).instances.append(self)

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def read(self, frames: int) -> tuple[list[int], None]:
        self.read_started.set()
        # Keep the worker alive long enough for the test to stop it.
        time.sleep(0.001)
        return ([0] * frames, None)


def install_fake_audio(monkeypatch: MonkeyPatch) -> None:
    FakeSoundFile.instances.clear()
    FakeInputStream.instances.clear()
    monkeypatch.setattr(
        sounddevice.sf,  # pyright: ignore[reportPrivateLocalImportUsage]
        "SoundFile",
        FakeSoundFile,
    )
    monkeypatch.setattr(
        sounddevice.sd,  # pyright: ignore[reportPrivateLocalImportUsage]
        "InputStream",
        FakeInputStream,
    )


def test_recorder_is_idle_before_start():
    recorder = SoundDeviceRecorder()

    assert not recorder.is_recording
    assert recorder.current_recording is None
    assert asyncio.run(recorder.stop_recording()) is None


def test_recording_writes_audio_reports_progress_and_returns_path(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    install_fake_audio(monkeypatch)
    recorder = SoundDeviceRecorder(samplerate=8000, channels=2, subtype="PCM_24")
    path = tmp_path / "recording.wav"
    progress: list[float] = []

    recorder.register_progress_callback(progress.append)
    asyncio.run(recorder.start_recording(path))

    assert FakeInputStream.instances[0].read_started.wait(timeout=1)
    assert recorder.is_recording
    assert recorder.current_recording == path

    returned_path = asyncio.run(recorder.stop_recording())

    assert returned_path == path
    assert not recorder.is_recording
    assert recorder.current_recording is None
    assert progress and all(isinstance(value, float) for value in progress)
    assert FakeSoundFile.instances[0].path == path
    assert FakeSoundFile.instances[0].options == {
        "mode": "w",
        "samplerate": 8000,
        "channels": 2,
        "subtype": "PCM_24",
    }
    assert FakeSoundFile.instances[0].writes
    assert FakeSoundFile.instances[0].closed
    assert FakeInputStream.instances[0].options == {
        "samplerate": 8000,
        "channels": 2,
        "dtype": "int16",
    }
    assert FakeInputStream.instances[0].closed


def test_start_while_recording_is_ignored(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    install_fake_audio(monkeypatch)
    recorder = SoundDeviceRecorder()
    first_path = tmp_path / "first.wav"
    second_path = tmp_path / "second.wav"

    asyncio.run(recorder.start_recording(first_path))
    assert FakeInputStream.instances[0].read_started.wait(timeout=1)
    asyncio.run(recorder.start_recording(second_path))

    assert recorder.current_recording == first_path
    assert len(FakeInputStream.instances) == 1
    assert asyncio.run(recorder.stop_recording()) == first_path
