# conftest.py
import time
import wave
from pathlib import Path
import pytest


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


# ---- fake OutputStream that just "accepts" writes ----
class FakeOutputStream:
    def __init__(self, samplerate, channels, sleep_per_write=0.005):
        self.samplerate = samplerate
        self.channels = channels
        self.sleep_per_write = sleep_per_write
        self.closed = False
        self.total_frames = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True

    def write(self, block):
        # Simulate time passing per block and count frames
        self.total_frames += len(block)
        time.sleep(self.sleep_per_write)


@pytest.fixture
def patch_sounddevice(monkeypatch):
    import sounddevice as sd

    monkeypatch.setattr(sd, "OutputStream", FakeOutputStream)
