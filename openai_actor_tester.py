import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from audio_player import AudioPlayer, SoundDevicePlayer
from chat_message import ChatMessage
from voice_actor import OpenAIVoiceActor, VoiceActor

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

    if actor.can_speak_out_loud:
        print("Stream speaking")
        actor.speak_message_out_load(message)
        print("Stream speaking done")
    else:
        print("File speaking")
        tmp: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory(
            prefix="rpg-test-voices"
        )
        temp_folder_path: Path = Path(tmp.name)
        path = actor.speak_message(message, temp_folder_path)
        audio_player: AudioPlayer = SoundDevicePlayer()

        def callback(path: Path):
            path.unlink(missing_ok=True)

        audio_player.register_finished_callback(callback)
        audio_player.play_file(path)
        while audio_player.is_playing:
            time.sleep(0.1)
        print("File speaking done")


if __name__ == "__main__":
    load_dotenv()
    main()
