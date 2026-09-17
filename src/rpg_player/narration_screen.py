from __future__ import annotations

import asyncio
import tempfile
import wave
from pathlib import Path

from rich.markdown import Markdown
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, RichLog, TextArea

from rpg_player.audio.sounddevice import SoundDeviceRecorder
from rpg_player.domain.audio_recorder import AudioRecorder
from rpg_player.domain.chat_message import ChatMessages
from rpg_player.domain.transcriber import AudioTranscriber, TranscriptionResult


class NarrationScreen(Screen):
    BINDINGS = [
        ("ctrl+r", "toggle_record", "Record/Stop"),
        ("ctrl+j", "accept", "Accept"),
        ("escape", "cancel", "Cancel"),
        ("ctrl+k", "clear", "Clear"),
    ]

    CSS = """
    #toolbar {
        padding: 0 1;
        height: auto;
    }
    #toolbar Button { margin: 0 1 0 0; }
    #toolbar Button.end { margin-right: 0; }

    #status {
        color: $text 50%;
        padding: 0 1;
    }
    RichLog {
        height: 0.5fr;
    }
    TextArea {
        height: 1fr;
        border: tall $accent 10%;
    }
    """

    def __init__(
        self,
        *,
        title: str = "Narration",
        transcriber: AudioTranscriber,
        messages: ChatMessages,
    ) -> None:
        super().__init__()
        self._title = title
        self._is_recording = False
        self._record_task = None
        self._chunk_idx = 0
        self.transcriber: AudioTranscriber = transcriber
        self.recorder: AudioRecorder = SoundDeviceRecorder()
        self.messages: ChatMessages = messages
        # Path to temporary audio file for the current recording
        self._current_audio_path: Path | None = None
        # Task used while recording (starts recorder.start_recording)
        self._record_task: asyncio.Task | None = self._record_task
        # Task used when running transcription (if any)
        self._transcribe_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            with Horizontal(id="toolbar"):
                yield Button("Record", id="btn-record", variant="primary")
                yield Button("Accept", id="btn-accept", variant="success")
                yield Button("Cancel", id="btn-cancel", variant="warning")
                yield Button("Clear", id="btn-clear", classes="end")
            yield RichLog(id="messages")
            yield Label("Ready.", id="status")
            yield TextArea(
                id="editor", language="markdown", tooltip="Narration text (editable)"
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title

        log: RichLog = self.query_one("#messages", RichLog)
        recent_msg_count = 10
        log.write(f"{recent_msg_count} recent messages: ")
        last_n_messages = self.messages.messages[-recent_msg_count:]
        for message in last_n_messages:
            text = f"**{message.author}**: {message.content}"
            md = Markdown(text)
            log.write(md)

        editor: TextArea = self.query_one(TextArea)
        # Don't set any initial text even if self._initial_text is set
        editor.text = ""
        editor.focus()

    async def start_recording_and_transcribe(self) -> None:
        if self._record_task and not self._record_task.done():
            return
        # Create a temporary WAV file for this recording session
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = Path(tmp.name)
        tmp.close()
        self._current_audio_path = tmp_path

        # Start the recorder writing to the temp file
        await self.recorder.start_recording(tmp_path)

        # create a task that simply waits while recording is active; used as a marker
        async def _recording_waiter():
            try:
                while self.recorder.is_recording:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass

        self._record_task = asyncio.create_task(_recording_waiter())

    async def stop_recording(self) -> None:
        # Stop the recorder and run transcription on the saved file.
        if self._current_audio_path is None:
            return

        # Stop the device recorder.  The returned path is important: a recorder
        # can fail in its worker thread (for example when the input device is
        # unavailable) while still leaving the temporary WAV file behind.  Do
        # not send that empty file to Whisper; silence/invalid audio commonly
        # produces convincing but unrelated hallucinations.
        try:
            stopped_path = await self.recorder.stop_recording()
        except Exception as e:
            self._set_status(f"Failed stopping recorder: {e}")
            stopped_path = None

        # Ensure any recording waiter task is finished
        if self._record_task and not self._record_task.done():
            self._record_task.cancel()
            try:
                await self._record_task
            except asyncio.CancelledError:
                pass

        audio_path = self._current_audio_path
        self._current_audio_path = None

        if (
            stopped_path is None
            or not audio_path
            or not audio_path.exists()
            or not self._contains_audio(audio_path)
        ):
            self._set_status(
                "No audio was recorded. Check the input device and microphone permissions."
            )
            if audio_path and audio_path.exists():
                audio_path.unlink(missing_ok=True)
            return

        # Prepare a handler to be called by streaming transcribers. The handler
        # may be invoked from a background thread, so schedule UI updates on the
        # main loop.
        loop = asyncio.get_running_loop()

        def stream_handler(result: TranscriptionResult) -> None:
            try:
                coro = self._append_transcription(result)
                # Schedule coroutine safely on the main loop
                loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))
            except Exception:
                # swallow handler exceptions to avoid breaking background thread
                pass

        # Run transcription in background so UI remains responsive.  Keep the
        # streaming call inside a coroutine so API errors are displayed rather
        # than becoming an unobserved exception in the cleanup task.
        transcribe_stream = getattr(self.transcriber, "transcribe_stream", None)
        if transcribe_stream is not None:

            async def _run_streaming_transcription():
                try:
                    await asyncio.to_thread(
                        transcribe_stream,
                        audio_path,
                        stream_handler,
                    )
                except Exception as e:
                    self._set_status(f"Transcription failed: {e}")

            self._transcribe_task = asyncio.create_task(_run_streaming_transcription())
        else:

            async def _run_full_transcription():
                try:
                    result = await asyncio.to_thread(
                        self.transcriber.transcribe, audio_path
                    )
                    await self._append_transcription(result)
                except Exception as e:
                    self._set_status(f"Transcription failed: {e}")

            self._transcribe_task = asyncio.create_task(_run_full_transcription())

        # Cleanup temp file after transcription completes
        async def _cleanup():
            try:
                if self._transcribe_task:
                    await self._transcribe_task
            finally:
                try:
                    audio_path.unlink()
                except Exception:
                    pass

        asyncio.create_task(_cleanup())

    @staticmethod
    def _contains_audio(path: Path) -> bool:
        """Return whether a WAV contains a non-silent recorded frame.

        A failed/default input device can still produce a perfectly valid WAV
        header containing only zero samples. Sending that file to a speech
        model is unsafe: transcription models may hallucinate text for silence.
        """
        try:
            with wave.open(str(path), "rb") as audio:
                if audio.getnframes() == 0:
                    return False
                # The recorder writes PCM16. Checking the raw bytes also avoids
                # adding a NumPy dependency just to calculate a signal level.
                return any(audio.readframes(audio.getnframes()))
        except (OSError, wave.Error):
            return False

    async def _append_transcription(self, result: TranscriptionResult) -> None:
        editor = self.query_one(TextArea)
        # TranscriptionResult.text is the complete transcription so far, not
        # merely the newly received delta.
        editor.text = result.text
        editor.cursor_location = (
            editor.document.end
        )  # move caret to end; TextArea auto-scrolls when cursor/selection changes

    async def action_toggle_record(self) -> None:
        if not self._is_recording:
            self._is_recording = True
            self._set_editor_locked(True)
            self._set_record_button_label("Stop")
            self._toggle_buttons()
            self._set_status("Recording… (locked). Press 'r' to stop.")
            await self.start_recording_and_transcribe()
        else:
            self._is_recording = False
            if self._record_task and not self._record_task.done():
                self._record_task.cancel()
                try:
                    await self._record_task
                except asyncio.CancelledError:
                    pass
            self._set_editor_locked(False)
            self._set_record_button_label("Record")
            self._toggle_buttons()
            self._set_status("Recording stopped. Editor unlocked.")
            await self.stop_recording()

    def action_clear(self) -> None:
        self.query_one(TextArea).text = ""
        self._set_status("Cleared.")

    def action_accept(self) -> None:
        text = self.query_one(TextArea).text
        self.dismiss(text)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed)
    async def handle_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-record":
            await self.action_toggle_record()
        elif bid == "btn-accept":
            self.action_accept()
        elif bid == "btn-cancel":
            self.action_cancel()
        elif bid == "btn-clear":
            self.action_clear()

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Label).update(text)

    def _toggle_buttons(self) -> None:
        # Disable actions that would conflict during recording
        self.query_one("#btn-accept", Button).disabled = self._is_recording
        self.query_one("#btn-clear", Button).disabled = self._is_recording

    def _set_editor_locked(self, locked: bool) -> None:
        editor = self.query_one(TextArea)
        editor.disabled = locked
        if not locked:
            editor.focus()

    def _set_record_button_label(self, text: str) -> None:
        self.query_one("#btn-record", Button).label = text
