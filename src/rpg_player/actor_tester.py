import logging
import tempfile
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from textual import on
from textual.app import App, ComposeResult
from textual.containers import HorizontalScroll, VerticalScroll
from textual.logging import TextualHandler
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, Rule, Select, TextArea

from .audio_player import AudioPlayer, SoundDevicePlayer
from .chat_message import ChatMessage
from .piper_voice_actor import PiperVoiceActor
from .voice_actor import VoiceActor


class ChooseSpeakerId(ModalScreen[str]):
    """
    Simple dialog screen for picking the speaker id
    """

    def __init__(self, speaker_ids: List[str]):
        super().__init__()
        self.speaker_ids = speaker_ids

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("Choose a Speaker:")
            options = [(s, s) for s in self.speaker_ids]
            select: Select[str] = Select(options)
            yield select

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        self.title = str(event.value)
        self.dismiss(event.value)


class VoiceActorScreen(Screen):
    TITLE = "Voice Actor Test"
    SUB_TITLE = "Test your voices"

    CSS = """
    #actor_buttons {
        padding: 0 1;
        height: auto;
    }
    #actor_buttons Button { margin: 0 1 0 0; }
    #actor_buttons Button.end { margin-right: 0; }

    #status {
        color: $text 50%;
        padding: 0 1;
    }
    TextArea {
        height: 1fr;
        border: tall $accent 10%;
    }
    """

    def __init__(self, actors: Dict[str, VoiceActor], audio_player: AudioPlayer):
        super().__init__()
        self.actors: Dict[str, VoiceActor] = actors
        self.audio_player: AudioPlayer = audio_player

        def delete_callback(path: Path):
            path.unlink(missing_ok=True)

        self.audio_player.register_finished_callback(delete_callback)

        self._tmp: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory(
            prefix="rpg-test-voices"
        )
        self.temp_folder_path: Path = Path(self._tmp.name)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Type example message below:")
        yield TextArea(id="editor", text="The quick brown fox jumps over the lazy dog.")
        yield Rule(line_style="thick")
        yield Label("Test Voice Actors:")
        with HorizontalScroll(id="actor_buttons"):
            for name, actor in self.actors.items():
                btn = Button(f"{actor.__class__.__name__}:\n{name}", classes="actor")
                btn.data = {"name": name}
                yield btn
        yield Label("Not tested anything yet", id="test_label")
        yield Footer()

    def on_mout(self) -> None:
        editor: TextArea = self.query_one(TextArea)
        editor.cursor_location = editor.document.end
        editor.focus()

    @on(Button.Pressed, "#actor_buttons .actor")
    async def handle_speak_button(self, event: Button.Pressed) -> None:
        info = getattr(event.button, "data", {}) or {}
        name: str = info.get("name")
        actor: VoiceActor = self.actors[name]
        if len(actor.speaker_names) > 1:
            speaker_names = sorted(list(actor.speaker_names))
            self.app.push_screen(
                ChooseSpeakerId(speaker_names),
                lambda result: self._after_choice(result, actor, name),
            )
        else:
            self._after_choice(list(actor.speaker_names)[0], actor, name)

    def _after_choice(self, result: str | None, actor: VoiceActor, name: str) -> None:
        if not result:
            return
        text_area: TextArea = self.query_one(TextArea)
        text: str = text_area.text
        message = ChatMessage.speech(result, text)
        label: Label = self.query_one("#test_label")
        label.update(f"Played: {name} with speaker id {result}")
        if actor.can_speak_out_loud:
            actor.speak_message_out_load(message)
        else:
            audio_path = actor.speak_message(message, self.temp_folder_path)
            self.audio_player.play_file(audio_path)


class VoiceActorTestApp(App):
    TITLE = "Voice Actor Test App"

    def on_ready(self) -> None:
        actors: Dict[str, VoiceActor] = {}
        actor1 = PiperVoiceActor.with_all_speaker_ids(
            "piper-models/en_US-lessac-medium.onnx"
        )
        actors["en_US-lessac-medium"] = actor1
        actor2 = PiperVoiceActor.with_all_speaker_ids(
            "piper-models/en_US-libritts-high.onnx"
        )
        actors["en_US-libritts-high"] = actor2

        audio_player = SoundDevicePlayer()
        va_screen = VoiceActorScreen(actors, audio_player)
        self.install_screen(va_screen, "va")
        self.push_screen("va")


if __name__ == "__main__":
    load_dotenv()
    logging.getLogger().addHandler(TextualHandler())
    app = VoiceActorTestApp()
    app.run()
