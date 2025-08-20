import logging
import os
import tempfile
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional, Set, Union, override

from openai import OpenAI
from piper.voice import PiperVoice, SynthesisConfig

from chat_message import ChatMessage, MessageType

log = logging.getLogger(__name__)


def _parse_names(names: Union[str, Iterable[str]]) -> Set[str]:
    # Normalize names into a set of casefolded strings
    if isinstance(names, str):
        norm_names: Set[str] = {names.casefold()}
    else:
        # Ensure it's an iterable of strings
        try:
            norm_names = {n.casefold() for n in names}  # type: ignore[arg-type]
        except TypeError:
            raise TypeError("names must be a string or an iterable of strings")
        if not all(isinstance(n, str) for n in names):  # type: ignore[iterable-issue]
            raise TypeError("all elements of 'names' must be strings")
    return norm_names


class VoiceActor(ABC):
    """
    A VoiceActor is a class that can speak messages.
    """

    @abstractmethod
    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        """
        Speak the given message, saving it to a file in the given path and
        returning the path to the file
        """

        raise NotImplementedError

    @abstractmethod
    def should_speak_message(self, message: ChatMessage) -> bool:
        """
        Return true if this voice actor should speak the message
        """
        raise NotImplementedError


class PiperVoiceActor(VoiceActor):
    """
    Voice Actor that uses the piper-tts library for voices.

    Piper models are relatively small, run locally and give okay output.
    They can run with just the CPU or be GPU accelerated.

    Piper models can contain multiple voices (known as speakers) or a single
    voice.
    """

    def __init__(
        self,
        names: Union[str, Iterable[str]],
        model_path: Path,
        speaker_id: Optional[int] = None,
    ):
        self.names: Set[str] = _parse_names(names)
        self.voice: PiperVoice = PiperVoice.load(str(model_path))
        self.syn_config = SynthesisConfig(speaker_id=speaker_id)
        self.speaker_map: dict = dict()

    def set_speaker_id_for(self, name: str, speaker_id: int):
        """
        Allows you to override the speaker_id for a given name.

        This is useful if the model used has multiple speakers and you want to
        reuse the single instance.
        """
        name = name.casefold()
        if name in self.names:
            self.speaker_map[name] = speaker_id
        else:
            raise ValueError(
                (
                    f"{name} is not a valid name for this actor, "
                    f"valid names are {self.names}"
                )
            )

    @override
    def should_speak_message(self, message: ChatMessage) -> bool:
        return (message.author.casefold() in self.names) and (
            message.type == MessageType.SPEECH
        )

    @override
    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(f"Speaking message {message.msg_id} with Piper")
        folder_path.mkdir(parents=True, exist_ok=True)

        out_path = None
        with tempfile.NamedTemporaryFile(
            dir=folder_path, suffix=".wav", delete=False
        ) as f:
            out_path = Path(f.name)

        text = (message.content or "").strip()

        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)  # Piper outputs mono
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(self.voice.config.sample_rate)

            if text:
                config = self.syn_config
                if message.author in self.speaker_map:
                    config = SynthesisConfig(
                        speaker_id=self.speaker_map[message.author]
                    )
                for chunk in self.voice.synthesize(text, syn_config=config):
                    wf.writeframes(chunk.audio_int16_bytes)
        return out_path


class EchoVoiceActor(VoiceActor):
    """
    A simple test VoiceActor that will echo out all messages to the log and
    save a text copy of them to a temporay file.
    """

    @override
    def should_speak_message(self, message: ChatMessage) -> bool:
        # Will speak all speech messages
        return message.type == MessageType.SPEECH

    @override
    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(f"Speaking message {message.msg_id} with Echo")
        path = None
        with tempfile.NamedTemporaryFile(
            dir=folder_path, suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as f:
            log.info(f"{message.author}: {message.content}")
            f.write(message.content)
            path = Path(f.name)
        return path


class OpenAIVoiceActor(VoiceActor):
    """
    OpenAI based voice actor.

    Will use the OpenAI TTS API to produce a voice.

    You will need to provide a model, the voice to use and the names of the
    authors this voice is for. You can and should also supply instructions as
    this will help the voice sound as intended.
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
        self.names: Set[str] = _parse_names(names)
        self.openai = openai
        self.model = model
        self.voice = voice
        self.response_format = response_format
        self.instructions = instructions
        try:
            self.file_suffix = self._SUFFIX[response_format]
        except KeyError:
            raise ValueError(f"Unsupported response_format: {response_format!r}")

    @override
    def should_speak_message(self, message: ChatMessage) -> bool:
        return (message.author.casefold() in self.names) and (
            message.type == MessageType.SPEECH
        )

    @override
    def speak_message(self, message: ChatMessage, folder_path: Path) -> Path:
        log.debug(f"Speaking message {message.msg_id} with OpenAI")
        folder_path.mkdir(parents=True, exist_ok=True)

        out_path = None
        with tempfile.NamedTemporaryFile(
            dir=folder_path, suffix=self.file_suffix, delete=False
        ) as f:
            out_path = Path(f.name)

        try:
            # Store keywords in a dict
            kw = {
                "model": self.model,
                "voice": self.voice,
                "input": message.content,
                "response_format": self.response_format,
            }
            if self.instructions:
                kw["instructions"] = self.instructions

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


class VoiceActorManager:
    """
    The VoiceActorManager holds all the VoiceActor instances and passes
    messages to them.
    """

    def __init__(self):
        self.actors: Set[VoiceActor] = set()
        self._tmp: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory(
            prefix="rpg-voices"
        )
        self._tmp_path = Path(self._tmp.name)

    def cleanup(self):
        """
        Will cleanup the temporary directory
        """
        self._tmp.cleanup()

    def register_actor(self, actor: VoiceActor):
        """
        Register a VoiceActor.

        The VoiceActor is responsible for deciding if a message is one it needs
        to speak and responsible for speaking.
        """
        if actor not in self.actors:
            log.debug(f"Registering actor: {actor}")
            self.actors.add(actor)

    def deregister_actor(self, actor: VoiceActor):
        """
        Deregister a VoiceActor if it is present.
        """
        if actor in self.actors:
            self.actors.remove(actor)

    def process_message(self, message: ChatMessage) -> List[Path]:
        """
        Given a message, process it, passing it to VoiceActor instances if
        needed.

        Will return a list of file paths for the voiced lines. This should
        normally be a single file, but multiple files may be written, either by
        differnt voice actors or the same voice actor.
        """
        log.debug(f"Processing message: {message.msg_id}")
        paths: List[Path] = []
        for actor in self.actors:
            if actor.should_speak_message(message):
                path = actor.speak_message(message, self._tmp_path)
                if path:
                    paths.append(path)
        return paths
