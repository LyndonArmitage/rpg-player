import time
from collections.abc import Iterable
from pathlib import Path
from random import Random
from typing import Callable, Final, override

from openai import Omit, OpenAI, omit
from openai.types.audio import (
    TranscriptionTextDeltaEvent,
    TranscriptionTextDoneEvent,
    TranscriptionTextSegmentEvent,
)

from rpg_player.domain.transcriber import (
    AudioTranscriber,
    StreamOutputAudioTranscriber,
    TranscriptionResult,
)


class OpenAIAudioTranscriber(AudioTranscriber, StreamOutputAudioTranscriber):
    """
    OpenAI Based Audio Transcriber.

    This class uses the OpenAI API for transcription.

    You can choose from the following models:
        - whisper-1
        - gpt-4o-transcribe
        - gpt-4o-mini-transcribe
        - gpt-live-transcribe
        - gpt-transcribe
    """

    def __init__(
        self,
        openai: OpenAI,
        model: str = "gpt-transcribe",
        language: str | None = "en",
        extra_prompt: str | None = None,
    ):
        self.openai: OpenAI = openai
        self.model: Final[str] = model
        self.language: Final[str | Omit] = language if language else omit
        self.prompt: Final[str | Omit] = extra_prompt if extra_prompt else omit

    @override
    def transcribe(self, file: Path) -> TranscriptionResult:
        """Transcribe an audio file using the OpenAI Whisper API."""
        if not file.exists():
            raise FileNotFoundError(f"Audio file does not exist: {file}")
        try:
            with file.open("rb") as audio_fp:
                response = self.openai.audio.transcriptions.create(
                    model=self.model,
                    file=audio_fp,
                    language=self.language,
                    prompt=self.prompt,
                )
            return TranscriptionResult(
                path=file, text=response.text, delta=response.text, completed=True
            )
        except Exception as e:
            raise RuntimeError("Transcription failed") from e

    @override
    def transcribe_stream(
        self, file: Path, handler: Callable[[TranscriptionResult], None]
    ) -> None:
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
                stream = self.openai.audio.transcriptions.create(
                    model=self.model,
                    file=audio_fp,
                    language=self.language,
                    prompt=self.prompt,
                    keywords=[],
                    stream=True,
                )
                gathered_text: str = ""
                for event in stream:
                    if isinstance(event, TranscriptionTextSegmentEvent):
                        segment_event: TranscriptionTextSegmentEvent = event
                        gathered_text += segment_event.text
                        result = TranscriptionResult(
                            path=file,
                            text=gathered_text,
                            delta=segment_event.text,
                            completed=False,
                        )
                        handler(result)
                    elif isinstance(event, TranscriptionTextDoneEvent):
                        done_event: TranscriptionTextDoneEvent = event
                        result = TranscriptionResult(
                            path=file,
                            text=done_event.text,
                            delta="",
                            completed=True,
                        )
                        handler(result)
                    else:
                        delta_event: TranscriptionTextDeltaEvent = event
                        delta = delta_event.delta
                        gathered_text += delta
                        result = TranscriptionResult(
                            path=file,
                            text=gathered_text,
                            delta=delta,
                            completed=False,
                        )
                        handler(result)
        except Exception as e:
            raise RuntimeError("Streaming transcription failed") from e


class DummyAudioTranscriber(AudioTranscriber, StreamOutputAudioTranscriber):
    """
    A Dummy implementation of AudioTranscriber.

    This will always output something from the given dummy text.

    The given dummy text could be a single line or multiple values, the random
    instance is used to pick from these.
    """

    def __init__(self, dummy_text: str | Iterable[str], random: Random | None = None):
        self.random: Random = random if random else Random()
        if isinstance(dummy_text, str):
            self.dummy_text: list[str] = [dummy_text]
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
    def transcribe(self, file: Path) -> TranscriptionResult:
        text = self._random_text()
        return TranscriptionResult(path=file, text=text, delta="", completed=True)

    @override
    def transcribe_stream(
        self, file: Path, handler: Callable[[TranscriptionResult], None]
    ) -> None:
        line_count = self.random.randint(1, 3)
        seperator = "\n"
        full_text: str = ""
        for _ in range(line_count):
            time.sleep(0.2)
            text = self._random_text() + seperator
            full_text += text
            result = TranscriptionResult(
                path=file, text=full_text, delta=text, completed=False
            )
            handler(result)
        final_result = TranscriptionResult(
            path=file, text=full_text, delta="", completed=True
        )
        handler(final_result)
