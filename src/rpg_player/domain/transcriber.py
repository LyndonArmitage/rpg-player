from pathlib import Path
from typing import Protocol


class AudioTranscriber(Protocol):
    """
    Protocol defining a simple audio transcription interface.

    The assumption is that this is a synchronous transcription, with the audio
    coming from a file, being fully transcribed, then the output being given.
    """

    def transcribe(self, file: Path) -> str:
        """
        Transcribe the audio from the given file and return the output as a
        string.

        This method is assumed to be blocking.
        """
        ...


# TODO: Add support for other modes of transcription e.g.
# file in -> stream out (async output)
# stream in -> stream out (async input and async output)
# stream in -> final string out (async input and sync output)

# Previously I supported async output
