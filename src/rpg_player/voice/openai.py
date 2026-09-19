import asyncio
import logging
import os
import tempfile
import threading
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, override

from openai import AsyncOpenAI, OpenAI
from openai.helpers import LocalAudioPlayer

from rpg_player.domain.chat_message import ChatMessage, MessageType
from rpg_player.domain.voice_actor import OutLoudVoiceActor, VoiceActor, parse_names

log = logging.getLogger(__name__)


class OpenAIVoiceActor(VoiceActor, OutLoudVoiceActor):
    """
    OpenAI based voice actor.

    Will use the OpenAI TTS API to produce a voice.

    You will need to provide a model, the voice to use and the names of the
    authors this voice is for. You can and should also supply instructions as
    this will help the voice sound as intended.

    See https://www.openai.fm/ for help and inspiration.
    """

    # Map for output type to suffixes
    _SUFFIX: Mapping[str, str] = {
        "wav": ".wav",
        "mp3": ".mp3",
        "opus": ".opus",  # Opus in Ogg container; .opus is widely recognized
        "flac": ".flac",
        "aac": ".aac",
        "pcm": ".pcm",  # raw PCM; be sure your player knows the rate/channels
    }

    def __init__(
        self,
        names: str | Iterable[str],
        openai: OpenAI,
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
        response_format: str = "wav",
        instructions: str | None = None,
    ):
        self.names: frozenset[str] = frozenset(parse_names(names))
        self.openai: OpenAI = openai
        self.model: Final[str] = model
        self.voice: Final[str] = voice
        self.response_format: Final[str] = response_format
        self.instructions: Final[str | None] = instructions
        try:
            self.file_suffix: Final[str] = self._SUFFIX[response_format]
        except KeyError as err:
            raise ValueError(
                f"Unsupported response_format: {response_format!r}"
            ) from err

        # Create an Async client using the OpenAI client
        api_key = getattr(openai, "api_key", None)
        base_url = getattr(openai, "base_url", None)
        self.async_openai: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @property
    @override
    def speaker_names(self) -> frozenset[str]:
        return self.names

    @override
    def should_speak(self, msg: ChatMessage) -> bool:
        return (msg.author.casefold() in self.names) and (
            msg.message_type == MessageType.SPEECH
        )

    def _create_kw_dict(self, message: ChatMessage) -> dict[str, str]:
        kw = {
            "model": self.model,
            "voice": self.voice,
            "input": message.content,
            "response_format": self.response_format,
        }
        if self.instructions:
            kw["instructions"] = self.instructions
        return kw

    @override
    def synthesize(self, msg: ChatMessage, output_dir: Path) -> Path:
        log.debug(f"Speaking message {msg.msg_id} with OpenAI")
        output_dir.mkdir(parents=True, exist_ok=True)

        out_path = None
        with tempfile.NamedTemporaryFile(
            dir=output_dir, suffix=self.file_suffix, delete=False
        ) as f:
            out_path = Path(f.name)

        # Store keywords in a dict
        kw = self._create_kw_dict(msg)
        try:
            with self.openai.audio.speech.with_streaming_response.create(
                **kw  # pyright: ignore[reportArgumentType]
                # TODO: Fix above ignore
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

    @override
    def speak_message_out_loud(self, msg: ChatMessage) -> None:
        kw = self._create_kw_dict(msg)
        # Override the format to be low-latency
        kw["response_format"] = "pcm"

        async def _play_async():
            async with self.async_openai.audio.speech.with_streaming_response.create(
                **kw  # pyright: ignore[reportArgumentType]
                # TODO: Fix above ignore
            ) as resp:
                await LocalAudioPlayer().play(resp)

        try:
            _ = asyncio.get_running_loop()

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
