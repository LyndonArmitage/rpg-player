#!/usr/bin/env python3
from dotenv import load_dotenv
from openai import OpenAI

from rpg_player.domain.chat_message import ChatMessage
from rpg_player.domain.voice_actor import VoiceActor
from rpg_player.voice.openai import OpenAIVoiceActor

# Voices are:
# alloy
# ash
# ballad
# coral
# echo
# fable
# onyx
# nova
# sage
# shimmer
# verse
VOICE = "coral"

# Instructions describe how the voice should sound
INSTRUCTIONS = """
Voice:
The voice should be deep, velvety, and effortlessly cool, like a late-night
jazz radio host.

Tone:
The tone is smooth, laid-back, and inviting, creating a relaxed and easygoing
atmosphere.

Personality:
The delivery exudes confidence, charm, and a touch of playful sophistication,
as if guiding the listener through a luxurious experience.
""".strip()


def main():
    openai = OpenAI()
    actor: VoiceActor = OpenAIVoiceActor(
        "Test", openai, model="gpt-4o-mini-tts", voice=VOICE, instructions=INSTRUCTIONS
    )
    text = "This is a test audio file."
    message: ChatMessage = ChatMessage.speech("Test", text)

    print("Stream speaking")
    actor.speak_message_out_loud(message)
    print("Stream speaking done")


if __name__ == "__main__":
    _ = load_dotenv()
    main()
