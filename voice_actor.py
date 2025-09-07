import asyncio
import logging
import os
import queue
import tempfile
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Union, override

import onnxruntime as ort
import sounddevice as sd
from openai import AsyncOpenAI, OpenAI
from openai.helpers import LocalAudioPlayer
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

    @property
    @abstractmethod
    def speaker_names(self) -> Set[str]:
        """
        The speaker names this voice actor will work for
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def can_speak_out_loud(self) -> bool:
        """
        True if this voice actor supports speaking out loud
        """
        return False

    @abstractmethod
    def speak_message_out_load(self, message: ChatMessage) -> None:
        """
        Speak the given message out loud. This will not save the message to a
        file but instead speak the message through the audio output device as
        soon as possible.

        Not all voice actors will be able to do this so you should check if it
        is possible first.
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

    @classmethod
    def with_all_speaker_ids(cls, model_path: Path) -> "PiperVoiceActor":
        """
        Create an instance with names corresponding to the voice integers
        """
        # Loads twice to get all speaker ids
        voice: PiperVoice = PiperVoice.load(str(model_path))
        speaker_count = voice.config.num_speakers
        voice = None
        id_map = {str(i): i for i in range(speaker_count)}
        output = cls(id_map.keys(), model_path)
        output.speaker_map = id_map
        return output

    def __init__(
        self,
        names: Union[str, Iterable[str]],
        model_path: Path,
        speaker_id: Optional[int] = None,
    ):
        self.names: Set[str] = _parse_names(names)
        self.supports_cuda: bool = (
            "CUDAExecutionProvider" in ort.get_available_providers()
        )
        self.voice: PiperVoice = PiperVoice.load(
            str(model_path), use_cuda=self.supports_cuda
        )
        self.syn_config = SynthesisConfig(speaker_id=speaker_id)
        self.speaker_map: Dict[str, int] = dict()
        self.number_of_speakers: int = self.voice.config.num_speakers

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

    @property
    @override
    def speaker_names(self) -> Set[str]:
        return self.names

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
                config = self._get_config_for_author(message.author)
                for chunk in self.voice.synthesize(text, syn_config=config):
                    wf.writeframes(chunk.audio_int16_bytes)
        return out_path

    def _get_config_for_author(self, author: str) -> SynthesisConfig:
        config = self.syn_config
        author_casefold = author.casefold()
        if author_casefold in self.speaker_map:
            config = SynthesisConfig(speaker_id=self.speaker_map[author_casefold])
        return config

    @property
    @override
    def can_speak_out_loud(self) -> bool:
        return True

    @override
    def speak_message_out_load(self, message: ChatMessage) -> None:
        text = (message.content or "").strip()
        if not text:
            return
        config = self._get_config_for_author(message.author)
        gen = self.voice.synthesize(text, syn_config=config)
        first_chunk = next(gen)
        assert first_chunk.sample_width == 2, "Expected 16-bit PCM"
        sample_rate = first_chunk.sample_rate
        channels = first_chunk.sample_channels or 1
        bytes_per_frame = channels * first_chunk.sample_width

        # Use a queue to fill with audio bytes
        fifo = queue.Queue(maxsize=32)
        playback_done = threading.Event()

        def producer():
            # total = 0
            b = first_chunk.audio_int16_bytes
            fifo.put(b)
            # total += len(b)
            buffered = 1
            for chunk in gen:
                b = chunk.audio_int16_bytes
                fifo.put(b)
                # total += len(b)
                buffered += 1
            fifo.put(None)

        # Start piper producing audio into the FIFO
        prod_thread = threading.Thread(target=producer, daemon=True)
        prod_thread.start()

        # This is the buffer that will be drained while speaking
        buffer = bytearray()
        saw_eos_during_prebuffer = False
        # Prebuffer some lines before playback begins
        prebuffer_chunk_count = 2
        for _ in range(prebuffer_chunk_count):
            item = fifo.get()
            if item is None:
                # Already finished the speaking
                fifo.put(None)
                saw_eos_during_prebuffer = True
                break
            buffer.extend(item)

        if saw_eos_during_prebuffer and not buffer:
            # Nothing to play
            prod_thread.join()
            return

        tail_silence_secs = 0.10
        tail_bytes_remaining = 0
        eos_seen = False

        # This call back will fill our device buffer from the byte buffer
        def callback(outdata, frames, time, status):
            nonlocal buffer, eos_seen, tail_bytes_remaining
            needed = frames * bytes_per_frame
            while len(buffer) < needed and not eos_seen:
                try:
                    item = fifo.get(timeout=2.0)
                except queue.Empty:
                    item = None
                    # treat as EOS if producer died

                if item is None:
                    # End of the stream of audio
                    eos_seen = True
                    tail_bytes_remaining = (
                        int(tail_silence_secs * sample_rate) * bytes_per_frame
                    )
                    break
                buffer.extend(item)

            # Fill outdata from buffer first
            n = min(len(buffer), needed)
            if n:
                outdata[:n] = buffer[:n]
                del buffer[:n]

            # If we still owe bytes for this callback, use silence

            remaining = needed - n
            if remaining > 0:
                if eos_seen and tail_bytes_remaining > 0:
                    z = min(remaining, tail_bytes_remaining)
                    outdata[n : n + z] = b"\x00" * z
                    tail_bytes_remaining -= z
                    n += z
                    remaining -= z

                # If we still have a shortfall (shouldn't happen), pad zeroes
                if remaining > 0:
                    outdata[n:needed] = b"\x00" * remaining

            # Stop only after we emit the full tail of silence
            if eos_seen and tail_bytes_remaining > 0 and len(buffer) == 0:
                playback_done.set()
                raise sd.CallbackStop

        def finished_callback():
            playback_done.set()

        with sd.RawOutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            latency="low",
            blocksize=512,
            callback=callback,
            finished_callback=finished_callback,
        ):
            prod_thread.join()
            playback_done.wait()


class EchoVoiceActor(VoiceActor):
    """
    A simple test VoiceActor that will echo out all messages to the log and
    save a text copy of them to a temporay file.
    """

    def __init__(self, names: Union[str, Iterable[str]]):
        self.names = _parse_names(names)

    @property
    @override
    def speaker_names(self) -> Set[str]:
        return self.names

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

    @property
    @override
    def can_speak_out_loud(self) -> bool:
        return False

    @override
    def speak_message_out_load(self, message: ChatMessage) -> None:
        raise NotImplementedError


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

        # Create an Async client using the OpenAI client
        api_key = getattr(openai, "api_key", None)
        base_url = getattr(openai, "base_url", None)
        self.async_openai = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @property
    @override
    def speaker_names(self) -> Set[str]:
        return self.names

    @override
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

    @override
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
    @override
    def can_speak_out_loud(self) -> bool:
        return True

    @override
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

    def process_message(self, message: ChatMessage) -> (bool, List[Path]):
        """
        Given a message, process it, passing it to VoiceActor instances if
        needed.

        Will return a tuple of a boolean and list of file paths for the
        voiced lines. The first boolean from the tuple indicates if any Voice
        Actor spoke (be it writing to a file or out loud).

        The list of files should normally be a single file, but multiple files
        may be written, either by differnt voice actors or the same voice actor.

        If voice actors can speak out loud, they will not return a file and
        will instead block this function while they speak.
        """
        log.debug(f"Processing message: {message.msg_id}")
        paths: List[Path] = []
        spoke: bool = False
        for actor in self.actors:
            if actor.should_speak_message(message):
                if actor.can_speak_out_loud:
                    actor.speak_message_out_load(message)
                    spoke = True
                else:
                    path = actor.speak_message(message, self._tmp_path)
                    if path:
                        paths.append(path)
                        spoke = True
        return (spoke, paths)
