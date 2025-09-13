import logging
import os
import tempfile
import wave
from pathlib import Path
from typing import Iterable, Set, Union, override

import sounddevice as sd
from elevenlabs.client import ElevenLabs

from chat_message import ChatMessage, MessageType
from voice_actor import VoiceActor

log = logging.getLogger(__name__)


class ElevenlabsVoiceActor(VoiceActor):
    """
    Voice Actor that uses Elevenlabs.io voices.

    You'll need to have an Elevenlabs client setup for this and reference the
    right voice_id (these can be copied from the platform).
    """

    def __init__(
        self,
        names: Union[str, Iterable[str]],
        elevenlabs: ElevenLabs,
        voice_id: str,
        model_id: str = "eleven_flash_v2_5",
    ):
        self.names: Set[str] = VoiceActor.parse_names(names)
        self.elevenlabs: ElevenLabs = elevenlabs
        self.voice_id: str = voice_id
        self.model_id: str = model_id

    @override
    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(
            f"Speaking message {message.msg_id} with ElevenLabs (voice={self.voice_id})"
        )
        folder_path.mkdir(parents=True, exist_ok=True)

        # 16kHz PCM hard coded for now
        output_file_format: str = "pcm_16000"
        # We'll be writing out to a WAV file for now
        suffix = ".wav"
        out_path = None
        with tempfile.NamedTemporaryFile(
            dir=folder_path, suffix=suffix, delete=False
        ) as f:
            out_path = Path(f.name)

        text = (message.content or "").strip()

        try:
            # Call the ElevenLabs streaming convert API and write chunks to file.
            response = self.elevenlabs.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                output_format=output_file_format,
                model_id=self.model_id,
                optimize_streaming_latency=2,
            )
            with wave.open(str(out_path), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                for chunk in response:
                    if chunk:
                        f.writeframes(chunk)
            return out_path
        except Exception:
            # Cleanup on failure
            try:
                if out_path and out_path.exists():
                    os.unlink(out_path)
            except OSError:
                # We can ignore this error and just raise the original one
                pass
            raise

    @override
    def should_speak_message(self, message: ChatMessage) -> bool:
        return (message.author.casefold() in self.names) and (
            message.type == MessageType.SPEECH
        )

    @property
    @override
    def speaker_names(self) -> Set[str]:
        return self.names

    @property
    @override
    def can_speak_out_loud(self) -> bool:
        return True

    @override
    def speak_message_out_load(self, message: ChatMessage) -> None:
        log.debug(
            f"Speaking message {message.msg_id} with ElevenLabs (voice={self.voice_id})"
        )
        text = (message.content or "").strip()
        output_file_format: str = "pcm_16000"
        audio = self.elevenlabs.text_to_speech.stream(
            voice_id=self.voice_id,
            model_id=self.model_id,
            output_format=output_file_format,
            text=text,
            optimize_streaming_latency=2,
        )
        with sd.RawOutputStream(
            samplerate=16000, channels=1, dtype="int16", blocksize=512, latency="low"
        ) as out:
            for chunk in audio:
                if chunk:
                    out.write(chunk)
