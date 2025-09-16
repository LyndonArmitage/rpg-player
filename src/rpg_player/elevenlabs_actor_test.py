import os
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from .audio_player import AudioPlayer, SoundDevicePlayer
from .chat_message import ChatMessage
from .elevenlabs_voice_actor import ElevenlabsVoiceActor
from .voice_actor import VoiceActor


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
