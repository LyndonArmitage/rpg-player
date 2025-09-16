import queue
import tempfile
import threading
import wave
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Union

import onnxruntime as ort
import sounddevice as sd
from piper.voice import PiperVoice, SynthesisConfig

from .voice_actor import VoiceActor
from .chat_message import ChatMessage, MessageType

log = logging.getLogger(__name__)


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
        self.names: Set[str] = VoiceActor.parse_names(names)
        self.supports_cuda: bool = (
            "CUDAExecutionProvider" in ort.get_available_providers()
        )
        self.voice: PiperVoice = PiperVoice.load(
            str(model_path), use_cuda=self.supports_cuda
        )
        self.syn_config = SynthesisConfig(speaker_id=speaker_id)
        self.speaker_map: Dict[str, int] = {}
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
    def speaker_names(self) -> Set[str]:
        return self.names

    def should_speak_message(self, message: ChatMessage) -> bool:
        return (message.author.casefold() in self.names) and (
            message.type == MessageType.SPEECH
        )

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
    def can_speak_out_loud(self) -> bool:
        return True

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
