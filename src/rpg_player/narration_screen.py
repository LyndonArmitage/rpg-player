from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.markdown import Markdown
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, RichLog, TextArea

from .audio_recorder import AudioRecorder, SoundDeviceRecorder
from .audio_transcriber import AudioTranscriber
from .chat_message import ChatMessages


@dataclass
class TranscriptionChunk:
    text: str
    is_done: bool


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
        self._current_audio_path: Optional[Path] = None
        # Task used while recording (starts recorder.start_recording)
        self._record_task: Optional[asyncio.Task] = self._record_task
        # Task used when running transcription (if any)
        self._transcribe_task: Optional[asyncio.Task] = None

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

        # Stop the device recorder
        try:
            await self.recorder.stop_recording()
        except Exception as e:
            self._set_status(f"Failed stopping recorder: {e}")

        # Ensure any recording waiter task is finished
        if self._record_task and not self._record_task.done():
            self._record_task.cancel()
            try:
                await self._record_task
            except asyncio.CancelledError:
                pass

        audio_path = self._current_audio_path
        self._current_audio_path = None

        if not audio_path or not audio_path.exists():
            self._set_status(
                "Recording finished, but no audio file available for transcription."
            )
            return

        # Prepare a handler to be called by streaming transcribers. The handler
        # may be invoked from a background thread, so schedule UI updates on the
        # main loop.
        loop = asyncio.get_running_loop()

        def stream_handler(file: Path, text: str, done: bool) -> None:
            try:
                coro = self._append_transcription(TranscriptionChunk(text, done))
                # Schedule coroutine safely on the main loop
                loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))
            except Exception:
                # swallow handler exceptions to avoid breaking background thread
                pass

        # Run transcription in background so UI remains responsive
        if self.transcriber.supports_async_out:
            # transcribe_async_out is synchronous in our transcriber; run it in a thread
            self._transcribe_task = asyncio.create_task(
                asyncio.to_thread(
                    self.transcriber.transcribe_async_out, audio_path, stream_handler
                )
            )
        else:

            async def _run_full_transcription():
                try:
                    text = await asyncio.to_thread(
                        self.transcriber.transcribe, audio_path
                    )
                    await self._append_transcription(TranscriptionChunk(text, True))
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

    async def _append_transcription(self, chunk: TranscriptionChunk) -> None:
        editor = self.query_one(TextArea)
        current = editor.text or ""
        if chunk.is_done:
            # replace all text with final output
            editor.text = chunk.text
        else:
            # append text
            editor.text = f"{current}{chunk.text}"
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
