from pathlib import Path

from rpg_player.domain.chat_message import ChatMessage
from rpg_player.voice.piper import PiperVoiceActor

TEST_MODEL_PATH: Path = Path("piper-models/en_US-lessac-medium.onnx")


def test_piper_should_speak():
    names = ["Bob"]
    actor = PiperVoiceActor(names, TEST_MODEL_PATH)
    message = ChatMessage.speech("Bob", "This is a test.")
    bad_message = ChatMessage.speech("Jerry", "This is a bad test.")
    narrate_message = ChatMessage.narration("DM", "It was a dark and stormy night")
    assert actor.should_speak(message), "Should have worked"
    assert not actor.should_speak(
        bad_message
    ), "Should not have worked for other person"
    assert not actor.should_speak(
        narrate_message
    ), "Should not have worked for narration"


def test_piper_speaking(tmp_path: Path):
    actor = PiperVoiceActor("Bob", TEST_MODEL_PATH)
    message = ChatMessage.speech("Bob", "This is a test.")
    path = actor.synthesize(message, tmp_path)

    assert len(list(tmp_path.iterdir())) == 1, "Missing file"
    assert path.exists(), f"{path} should exist"
    assert path.stat().st_size > 0, "File should not be empty"
