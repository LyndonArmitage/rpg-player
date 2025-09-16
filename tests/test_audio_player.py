import time
from pathlib import Path

from rpg_player.audio_player import SoundDevicePlayer


def test_play_and_progress(temp_wav: Path, patch_sounddevice):
    calls = []

    def on_progress(current, total):
        calls.append((current, total))

    player = SoundDevicePlayer(blocksize=512)
    player.register_progress_callback(on_progress)
    started = player.play_file(temp_wav)
    assert started

    # Wait for playback to finish (with timeout safeguard)
    t0 = time.time()
    while player.is_playing and (time.time() - t0) < 5.0:
        time.sleep(0.01)

    # Finished; we should have at least one progress callback and total set
    assert calls, "Expected at least one progress callback"
    # last callback should be close to duration
    last_current, last_total = calls[-1]
    assert last_total > 0
    assert last_current <= last_total + 1e-3


def test_pause_resume_blocks_progress(temp_wav: Path, patch_sounddevice):
    calls = []

    def on_progress(current, total):
        calls.append((current, total))

    player = SoundDevicePlayer(blocksize=256)
    player.register_progress_callback(on_progress)
    assert player.play_file(temp_wav)

    # Let a little progress happen
    time.sleep(0.05)

    player.pause()

    # Wait until the player transitions to paused (ack the pause)
    t0 = time.time()
    while not player.is_paused and (time.time() - t0) < 1.0:
        time.sleep(0.001)

    paused_len = len(calls)

    time.sleep(0.05)
    assert len(calls) == paused_len, "Progress advanced while paused"

    player.resume()
    t0 = time.time()
    while player.is_playing and (time.time() - t0) < 5.0:
        time.sleep(0.01)


def test_stop_mid_playback(temp_wav: Path, patch_sounddevice):
    calls = []

    def on_progress(current, total):
        calls.append((current, total))

    player = SoundDevicePlayer(blocksize=512)
    player.register_progress_callback(on_progress)
    assert player.play_file(temp_wav)

    # Let a few blocks play then stop
    time.sleep(0.03)
    player.stop_audio()

    # Player should not be playing now
    assert not player.is_playing
