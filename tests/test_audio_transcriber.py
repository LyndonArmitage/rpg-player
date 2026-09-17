import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import cast

from openai import OpenAI

from rpg_player.audio_transcriber import OpenAIAudioTranscriber
from rpg_player.domain.transcriber import TranscriptionResult


class Event:
    def __init__(self, delta: str):
        self.delta: str = delta


class FakeResponse:
    def __init__(self, text: str):
        self.text: str = text


class FakeTranscriptions:
    def __init__(self, response: FakeResponse | Iterator[Event]):
        self.response: FakeResponse | Iterator[Event] = response

    def create(self, **_kwargs: object) -> FakeResponse | Iterator[Event]:
        return self.response


class FakeAudio:
    def __init__(self, transcriptions: FakeTranscriptions):
        self.transcriptions: FakeTranscriptions = transcriptions


class FakeOpenAI:
    def __init__(self, transcriptions: FakeTranscriptions):
        self.audio: FakeAudio = FakeAudio(transcriptions)


def test_transcribe_returns_expected_text():
    # Prepare dummy file
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        _ = tf.write(b"dummy audio content")
        file_path = Path(tf.name)

    mock_openai = cast(
        OpenAI, cast(object, FakeOpenAI(FakeTranscriptions(FakeResponse("foo bar"))))
    )
    transcriber = OpenAIAudioTranscriber(mock_openai)
    result = transcriber.transcribe(file_path)
    assert isinstance(result, TranscriptionResult)
    assert result.text == "foo bar"
    assert result.delta == "foo bar"
    assert result.completed is True

    _ = file_path.unlink()

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        _ = tf.write(b"dummy audio content")
        file_path = Path(tf.name)

    # Create event stream to yield 'A ', 'B ', 'C'
    events = [Event("A "), Event("B "), Event("C")]
    mock_openai = cast(
        OpenAI, cast(object, FakeOpenAI(FakeTranscriptions(iter(events))))
    )

    transcriber = OpenAIAudioTranscriber(mock_openai, model="gpt-4o-mini-transcribe")

    chunks: list[str] = []
    fulls: list[str] = []

    def handler(result: TranscriptionResult):
        if result.completed:
            fulls.append(result.text)
        else:
            chunks.append(result.delta)

    transcriber.transcribe_stream(file_path, handler=handler)
    assert chunks == ["A ", "B ", "C"]
    assert fulls == []
    _ = file_path.unlink()
