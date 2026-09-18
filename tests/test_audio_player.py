from __future__ import annotations

import time
from pathlib import Path

import pytest

from rpg_player.audio.sounddevice import SoundDevicePlayer
from tests.audio_fakes import FakeOutputStream


def wait_for_stream(timeout: float = 1.0) -> FakeOutputStream:
    deadline = time.monotonic() + timeout
    while not FakeOutputStream.instances and time.monotonic() < deadline:
        time.sleep(0.001)
    assert FakeOutputStream.instances
    return FakeOutputStream.instances[0]


def wait_until_stopped(player: SoundDevicePlayer, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while player.is_playing and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not player.is_playing


def test_play_and_report_progress(temp_wav: Path) -> None:
    progress: list[tuple[float, float]] = []
    finished: list[Path] = []
    player = SoundDevicePlayer(blocksize=512)
    player.register_progress_callback(
        lambda current, total: progress.append((current, total))
    )
    player.register_finished_callback(finished.append)

    assert player.play_file(temp_wav)
    wait_until_stopped(player)

    assert progress
    assert progress[0][0] == 0.0
    assert progress[-1][0] == pytest.approx(progress[-1][1])
    assert progress[-1][1] == pytest.approx(0.25, abs=0.01)
    assert finished == [temp_wav]
    assert FakeOutputStream.instances[0].closed


def test_cannot_start_a_second_file_while_playing(temp_wav: Path) -> None:
    player = SoundDevicePlayer(blocksize=64)
    assert player.play_file(temp_wav)
    stream = wait_for_stream()
    assert stream.started.is_set()

    assert not player.play_file(temp_wav)
    player.stop_audio()
    assert not player.is_playing


def test_stop_audio_finishes_playback_and_calls_callback(temp_wav: Path) -> None:
    finished: list[Path] = []
    player = SoundDevicePlayer(blocksize=64)
    player.register_finished_callback(finished.append)

    assert player.play_file(temp_wav)
    stream = wait_for_stream()
    assert stream.started.is_set()
    player.stop_audio()

    assert not player.is_playing
    assert finished == [temp_wav]


def test_missing_file_is_not_started(tmp_path: Path) -> None:
    player = SoundDevicePlayer()

    assert not player.play_file(tmp_path / "missing.wav")
    assert not player.is_playing
    assert not FakeOutputStream.instances


def test_constructor_rejects_invalid_buffer_settings() -> None:
    with pytest.raises(ValueError, match="blocksize"):
        _ = SoundDevicePlayer(blocksize=0)
    with pytest.raises(ValueError, match="buffersize"):
        _ = SoundDevicePlayer(buffersize=0)
