import time
from abc import ABC, abstractmethod
from pathlib import Path
from random import Random
from typing import Callable, Iterable, List, Optional, Union, override

from openai import OpenAI


class AudioTranscriber(ABC):
    """
    Base Audio Transcriber class.

    This should take a file (normally WAV file) and return the transcription
    from

    The transcription should just be what was spoken with no timestamps.
    """

    @abstractmethod
    def transcribe(self, file: Path) -> str:
        """
        Transcribe an audio file, returning the output at the end.

        This method is blocking.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def supports_async_out(self) -> bool:
        """
        Whether this supports async output or not
        """
        raise NotImplementedError

    @abstractmethod
    def transcribe_async_out(
        self, file: Path, handler: Callable[[Path, str, bool], None]
    ):
        """
        Transcribe an audio file, returning the output via a handler.

        The handler can be called multiple times and should take in the path of
        the file, the transcribed text, and a flag to say if transcription was
        completed or not.
        """
        raise NotImplementedError


class OpenAIAudioTranscriber(AudioTranscriber):
    def __init__(
        self,
        openai: OpenAI,
        model: str = "whisper-1",
        language: str = "en",
        extra_kwargs: Optional[dict] = None,
    ):
        """
        :param openai: OpenAI SDK client
        :param model: Name of Whisper model to use (default: "whisper-1")
        :param language: Language name, should be 2 character code (default: "en")
        :param extra_kwargs: Extra keyword arguments for transcription API call
        """
        self.openai = openai
        self.model = model

        self.language = language
        reserved_keys = {"model", "file", "language", "stream"}
        extra_kwargs = extra_kwargs or {}
        intersection = reserved_keys & extra_kwargs.keys()
        if intersection:
            raise ValueError(
                (
                    "extra_kwargs contains reserved keyword(s) "
                    f"that will be overwritten: {sorted(intersection)}"
                )
            )
        # All parameters that will be passed to API
        self.transcription_kwargs = {"model": model, "language": language}
        self.transcription_kwargs.update(extra_kwargs)

    @override
    def transcribe(self, file: Path) -> str:
        """Transcribe an audio file using the OpenAI Whisper API."""
        if not file.exists():
            raise FileNotFoundError(f"Audio file does not exist: {file}")
        try:
            with file.open("rb") as audio_fp:
                response = self.openai.audio.transcriptions.create(
                    file=audio_fp,
                    **self.transcription_kwargs,
                )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {e}")

    @property
    @override
    def supports_async_out(self) -> bool:
        """Whether async transcription is supported (streaming via OpenAI API)."""
        return self.model != "whisper-1"

    @override
    def transcribe_async_out(
        self, file: Path, handler: Callable[[Path, str, bool], None]
    ):
        """
        Streams transcription chunks from the OpenAI API and calls the handler
        for each chunk.
        """
        if self.model == "whisper-1":
            raise ValueError("whisper-1 model does not support streaming")
        if not file.exists():
            raise FileNotFoundError(f"Audio file does not exist: {file}")
        try:
            with file.open("rb") as audio_fp:
                stream_kwargs = dict(self.transcription_kwargs)
                stream_kwargs["stream"] = True
                stream = self.openai.audio.transcriptions.create(
                    file=audio_fp,
                    **stream_kwargs,
                )
                full_text = ""
                for event in stream:
                    delta = getattr(event, "delta", None)
                    # event type could be 'transcript.text.delta' or
                    # 'transcript.text.done', etc.
                    # Only handle 'delta' events incrementally
                    if delta:
                        full_text += delta
                        handler(file, delta, False)
                # At the end, report everything with done=True
                handler(file, full_text, True)
        except Exception as e:
            raise RuntimeError(f"Streaming transcription failed: {e}")


class DummyAudioTranscriber(AudioTranscriber):
    """
    A Dummy implementation of AudioTranscriber.

    This will always output something from the given dummy text.

    The given dummy text could be a single line or multiple values, the random
    instance is used to pick from these.
    """

    def __init__(
        self, dummy_text: Union[str, Iterable[str]], random: Optional[Random] = None
    ):
        if random:
            self.random: Random = random
        else:
            self.random: Random = Random()
        if isinstance(dummy_text, str):
            self.dummy_text: List[str] = [dummy_text]
        else:
            self.dummy_text = [str(t) for t in dummy_text]
        self._dummy_len: int = len(self.dummy_text)
        if self._dummy_len <= 0:
            raise ValueError("Must have at least 1 line of dummy text")

    def _random_text(self) -> str:
        if self._dummy_len == 1:
            return self.dummy_text[0]
        else:
            n = self.random.randint(0, self._dummy_len - 1)
            return self.dummy_text[n]

    @override
    def transcribe(self, file: Path) -> str:
        return self._random_text()

    @property
    @override
    def supports_async_out(self) -> bool:
        return True

    @override
    def transcribe_async_out(
        self, file: Path, handler: Callable[[Path, str, bool], None]
    ):
        line_count = self.random.randint(1, 3)
        seperator = "\n"
        for _ in range(line_count):
            time.sleep(0.2)
            text = self._random_text() + seperator
            handler(file, text, False)
        handler(file, "", True)
