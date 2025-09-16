import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

from rpg_player.audio_transcriber import OpenAIAudioTranscriber


def test_transcribe_returns_expected_text(monkeypatch):
    # Prepare dummy file
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"dummy audio content")
        file_path = Path(tf.name)

    # Mock response
    mock_response = MagicMock()
    mock_response.text = "foo bar"
    mock_openai = Mock()
    mock_openai.audio.transcriptions.create.return_value = mock_response

    transcriber = OpenAIAudioTranscriber(mock_openai)
    text = transcriber.transcribe(file_path)
    assert text == "foo bar"

    file_path.unlink()

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"dummy audio content")
        file_path = Path(tf.name)

    # Create event stream to yield 'A ', 'B ', 'C'
    class Event:
        def __init__(self, delta=None):
            self.delta = delta

    events = [Event("A "), Event("B "), Event("C")]
    mock_openai = Mock()
    mock_openai.audio.transcriptions.create.return_value = iter(events)

    transcriber = OpenAIAudioTranscriber(mock_openai, model="gpt-4o-mini-transcribe")

    chunks = []
    fulls = []

    def handler(path, text, done):
        if done:
            fulls.append(text)
        else:
            chunks.append(text)

    transcriber.transcribe_async_out(file_path, handler=handler)
    # Should call for each chunk, and once at end with full text
    assert chunks == ["A ", "B ", "C"]
    assert fulls == ["A B C"]
    file_path.unlink()
