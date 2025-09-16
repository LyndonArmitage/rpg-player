import asyncio
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Iterable, Optional, Set, Union

from openai import AsyncOpenAI, OpenAI
from openai.helpers import LocalAudioPlayer

from .voice_actor import VoiceActor
from .chat_message import ChatMessage, MessageType

log = logging.getLogger(__name__)


class OpenAIVoiceActor(VoiceActor):
    """
    OpenAI based voice actor.

    Will use the OpenAI TTS API to produce a voice.

    You will need to provide a model, the voice to use and the names of the
    authors this voice is for. You can and should also supply instructions as
    this will help the voice sound as intended.

    See https://www.openai.fm/ for help and inspiration.
    """

    # Map for output type to suffixes
    _SUFFIX = {
        "wav": ".wav",
        "mp3": ".mp3",
        "opus": ".opus",  # Opus in Ogg container; .opus is widely recognized
        "flac": ".flac",
        "aac": ".aac",
        "pcm": ".pcm",  # raw PCM; be sure your player knows the rate/channels
    }

    def __init__(
        self,
        names: Union[str, Iterable[str]],
        openai: OpenAI,
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
        response_format: str = "wav",
        instructions: Optional[str] = None,
    ):
        self.names: Set[str] = VoiceActor.parse_names(names)
        self.openai = openai
        self.model = model
        self.voice = voice
        self.response_format = response_format
        self.instructions = instructions
        try:
            self.file_suffix = self._SUFFIX[response_format]
        except KeyError:
            raise ValueError(f"Unsupported response_format: {response_format!r}")

        # Create an Async client using the OpenAI client
        api_key = getattr(openai, "api_key", None)
        base_url = getattr(openai, "base_url", None)
        self.async_openai = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @property
    def speaker_names(self) -> Set[str]:
        return self.names

    def should_speak_message(self, message: ChatMessage) -> bool:
        return (message.author.casefold() in self.names) and (
            message.type == MessageType.SPEECH
        )

    def _create_kw_dict(self, message: ChatMessage) -> dict:
        kw = {
            "model": self.model,
            "voice": self.voice,
            "input": message.content,
            "response_format": self.response_format,
        }
        if self.instructions:
            kw["instructions"] = self.instructions
        return kw

    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(f"Speaking message {message.msg_id} with OpenAI")
        folder_path.mkdir(parents=True, exist_ok=True)

        out_path = None
        with tempfile.NamedTemporaryFile(
            dir=folder_path, suffix=self.file_suffix, delete=False
        ) as f:
            out_path = Path(f.name)

        # Store keywords in a dict
        kw = self._create_kw_dict(message)
        try:
            with self.openai.audio.speech.with_streaming_response.create(
                **kw
            ) as response:
                response.stream_to_file(out_path)
            return out_path
        except Exception:
            # Failed for some reason, cleanup file
            try:
                os.unlink(out_path)
            except OSError:
                pass
            raise

    @property
    def can_speak_out_loud(self) -> bool:
        return True

    def speak_message_out_load(self, message: ChatMessage) -> None:
        kw = self._create_kw_dict(message)
        # Override the format to be low-latency
        kw["response_format"] = "pcm"

        async def _play_async():
            async with self.async_openai.audio.speech.with_streaming_response.create(
                **kw
            ) as resp:
                await LocalAudioPlayer().play(resp)

        try:
            asyncio.get_running_loop()

            def runner():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_play_async())
                finally:
                    loop.close()

            threading.Thread(target=runner, daemon=True).start()
        except RuntimeError:
            # Not running inn loop, so run it directly and block until done
            asyncio.run(_play_async())
