import time
from abc import ABC, abstractmethod, override
from pathlib import Path
from random import Random
from typing import Callable, Iterable, List, Optional, Union


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
