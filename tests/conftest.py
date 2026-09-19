# conftest.py
from __future__ import annotations

import wave
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tests.audio_fakes import FakeOutputStream


# ---- create a tiny WAV file (44.1 kHz mono, PCM16) without numpy ----
@pytest.fixture
def temp_wav(tmp_path: Path) -> Path:
    path = tmp_path / "silence.wav"
    samplerate = 44100
    duration_sec = 0.25  # short, but has a few blocks
    n_frames = int(samplerate * duration_sec)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(samplerate)
        wf.writeframes(b"\x00\x00" * n_frames)  # silence
    return path


@pytest.fixture(autouse=True)
def fake_output_stream(monkeypatch: MonkeyPatch) -> None:
    FakeOutputStream.instances.clear()
    import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]

    monkeypatch.setattr(sd, "RawOutputStream", FakeOutputStream)
