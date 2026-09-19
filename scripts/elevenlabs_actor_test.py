#!/usr/bin/env python3
import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from rpg_player.domain.chat_message import ChatMessage
from rpg_player.domain.voice_actor import VoiceActor
from rpg_player.voice.elevenlabs import ElevenlabsVoiceActor


def main():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs = ElevenLabs(api_key=api_key)
    voice_id = "YXpFCvM1S3JbWEJhoskW"
    model_id = "eleven_flash_v2_5"
    actor: VoiceActor = ElevenlabsVoiceActor(
        "test", elevenlabs, voice_id, model_id=model_id
    )
    text = "This is a test audio file."
    message: ChatMessage = ChatMessage.speech("Test", text)

    print("Stream speaking")
    actor.speak_message_out_loud(message)
    print("Stream speaking done")


if __name__ == "__main__":
    _ = load_dotenv()
    main()
