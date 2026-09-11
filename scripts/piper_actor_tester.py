#!/usr/bin/env python3

from pathlib import Path

from dotenv import load_dotenv

from rpg_player.domain.chat_message import ChatMessage
from rpg_player.domain.voice_actor import VoiceActor
from rpg_player.voice.piper import PiperVoiceActor


def main():
    model_path = Path("piper-models/en_US-lessac-medium.onnx")
    actor: VoiceActor = PiperVoiceActor("test", model_path)
    text = "This is a test audio file."
    message: ChatMessage = ChatMessage.speech("Test", text)
    print("Stream speaking")
    actor.speak_message_out_loud(message)
    print("Stream speaking done")


if __name__ == "__main__":
    _ = load_dotenv()
    main()
