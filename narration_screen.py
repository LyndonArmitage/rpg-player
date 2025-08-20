from __future__ import annotations

import asyncio
from dataclasses import dataclass


from textual import on
from textual.screen import Screen
from textual.widgets import Button, Label, TextArea, Footer, Header
from textual.containers import Horizontal, Vertical
from textual.app import ComposeResult


@dataclass
class TranscriptionChunk:
    text: str


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
    TextArea {
        height: 1fr;
        border: tall $accent 10%;
    }
    """

    def __init__(self, *, title: str = "Narration") -> None:
        super().__init__()
        self._title = title
        self._is_recording = False
        self._record_task = None
        self._chunk_idx = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            with Horizontal(id="toolbar"):
                yield Button("Record", id="btn-record", variant="primary")
                yield Button("Accept", id="btn-accept", variant="success")
                yield Button("Cancel", id="btn-cancel", variant="warning")
                yield Button("Clear", id="btn-clear", classes="end")
            yield Label("Ready.", id="status")
            yield TextArea(
                id="editor", language="markdown", tooltip="Narration text (editable)"
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        editor = self.query_one(TextArea)
        # Don't set any initial text even if self._initial_text is set
        editor.text = ""
        editor.focus()

    async def start_recording_and_transcribe(self) -> None:
        if self._record_task and not self._record_task.done():
            return
        self._record_task = asyncio.create_task(self._stream_transcription())

    async def _stream_transcription(self) -> None:
        pool = [
            "The quick brown fox",
            "jumps over the lazy dog",
            "and then pauses for breath",
            "before continuing the story",
            "about narrated adventures",
            "and clear, concise diction",
        ]
        try:
            while self._is_recording:
                text = pool[self._chunk_idx % len(pool)]
                suffix = "." if (self._chunk_idx % 3 == 2) else ""
                self._chunk_idx += 1
                await self._append_transcription(TranscriptionChunk(f"{text}{suffix}"))
                await asyncio.sleep(0.6)
        except asyncio.CancelledError:
            pass

    async def stop_recording(self) -> None:
        # Do not append anything to the textbox when stopping recording
        pass

    async def _append_transcription(self, chunk: TranscriptionChunk) -> None:
        editor = self.query_one(TextArea)
        current = editor.text or ""
        prefix = "\n" if current and not current.endswith("\n") else ""
        editor.text = f"{current}{prefix}{chunk.text}"
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
