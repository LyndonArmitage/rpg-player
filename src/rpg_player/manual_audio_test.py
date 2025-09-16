import math
import struct
import tempfile
import wave
from pathlib import Path

from .audio_player import SoundDevicePlayer


def generate_sine_wave(
    filename: Path,
    frequency: float = 440.0,
    duration: float = 2.0,
    samplerate: int = 44100,
    amplitude: float = 0.5,
):
    n_frames = int(samplerate * duration)
    with wave.open(str(filename), "w") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(samplerate)
        for i in range(n_frames):
            value = int(
                amplitude * 32767.0 * math.sin(2 * math.pi * frequency * i / samplerate)
            )
            wf.writeframesraw(struct.pack("<h", value))


def main():
    # This is a simple test to check that the sound player actually generates
    # sound, use your ears

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "sine.wav"
        generate_sine_wave(tmp_path)

        def on_progress(cur, total):
            print(f"{cur:.2f}/{total:.2f}s", end="\r")

        p = SoundDevicePlayer(blocksize=1024)
        p.register_progress_callback(on_progress)
        p.play_file(tmp_path)
        input("Press Enter to pause...")
        p.pause()
        input("Press Enter to resume...")
        p.resume()
        input("Press Enter to stop...")
        p.stop_audio()


if __name__ == "__main__":
    main()
