from pathlib import Path
from typing import Callable, NamedTuple, Protocol


class TranscriptionResult(NamedTuple):
    """Result of a transcription"""

    path: Path
    """The path of the file being transcribed"""

    text: str
    """
    The transcribed text so far.

    This will be the complete transcription when completed is true.
    """

    delta: str
    """
    The newly transcribed text.

    In the case of non-streaming output, this should match the completed text
    """

    completed: bool
    """Whether this is the last transcribed and complete output or not"""


class AudioTranscriber(Protocol):
    """
    Protocol defining a simple audio transcription interface.

    The assumption is that this is a synchronous transcription, with the audio
    coming from a file, being fully transcribed, then the output being given.
    """

    def transcribe(self, file: Path) -> TranscriptionResult:
        """
        Transcribe the audio from the given file and return the output as a
        result object.

        This method is assumed to be blocking.

        The output tuple of this function should be marked as completed. If it
        is not, then it may be a partial transcription due to some partial
        success in the transcriber.
        """
        ...


# TODO: Add support for other modes of transcription if needed e.g.
# stream in -> stream out
# stream in -> final string out
# Streaming input will be interesting as it means the transcriber will need to
# be able to listen to input from a device


class StreamOutputAudioTranscriber(Protocol):
    """
    Protocol defining an audio transcription interface that can take an audio
    file and transcribe it out live to a handler.
    """

    def transcribe_stream(
        self, file: Path, handler: Callable[[TranscriptionResult], None]
    ) -> None:
        """
        Transcribe an audio file, returning the output multiple times to the
        given handler as it is transcribed.

        The handler can be called multiple times and should take in the path of
        the file, the transcribed text, and a flag to say if it is the completed
        or not.

        The text passed back to the handler will be the full transcribed text
        so far as well as a delta.
        """
        ...
