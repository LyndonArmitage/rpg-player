import asyncio
import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from random import Random
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from rich.markdown import Markdown
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalGroup
from textual.events import Resize
from textual.logging import TextualHandler
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, RichLog, Rule, Switch

from agent import Agent, OpenAIAgent
from audio_transcriber import AudioTranscriber, OpenAIAudioTranscriber
from chat_message import ChatMessage
from config import Config
from narration_screen import NarrationScreen
from state_machine import StateMachine
from voice_actor import PiperVoiceActor, VoiceActor, VoiceActorManager


class Standby(Screen):

    TITLE = "RPG Party"
    SUB_TITLE = "Standby"
    CSS_PATH = "standby.tcss"
    BINDINGS = [
        ("0", "enter_narrate", "Narrate"),
        ("1", "agent_1_respond", "Agent 1 Respond"),
        ("2", "agent_2_respond", "Agent 2 Respond"),
        ("3", "agent_3_respond", "Agent 3 Respond"),
        ("a", "random_respond", "Random Respond"),
        ("r", "random_not_last_respond", "Not Last Respond"),
    ]

    def __init__(self, state_machine: StateMachine, transcriber: AudioTranscriber):
        super().__init__()
        self.state_machine: StateMachine = state_machine
        self.agent_names = state_machine.agent_names
        self.random: Random = Random()
        self._disable_bindings = threading.Event()
        self.rendered_messages: list = []
        self.transcriber: AudioTranscriber = transcriber

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="messages", wrap=True)
        yield Rule(line_style="thick")
        yield Label("Nothing has happened yet...", id="status")
        with Horizontal(id="buttons"):
            yield Button("Narrate", id="narrate")
            for i, agent_name in enumerate(self.agent_names):
                btn = Button(f"{i+1}: {agent_name}", id=f"agent{i}", classes="agent")
                btn.data = {"index": i, "name": agent_name}
                yield btn
            yield Button("Random Respond", id="random")
            yield Button("Not Last Respond", id="not-last")
            with VerticalGroup():
                yield Label("Toggle Speaking")
                yield Switch(id="speak-switch", tooltip="Toggle Speaking", value=True)
        yield Footer()

    def on_mount(self) -> None:
        # Make sure any pre-made messages are visible
        for msg in self.state_machine.messages:
            text = f"**{msg.author}:** {msg.content}"
            self.add_message(text)

    @on(Button.Pressed, "#buttons #narrate")
    def handle_narrate(self, _: Button.Pressed):
        self.action_enter_narrate()

    @on(Button.Pressed, "#buttons .agent")
    def handle_agent(self, event: Button.Pressed):
        info = getattr(event.button, "data", {}) or {}
        index = info.get("index")
        self.action_agent_respond(index)

    @on(Button.Pressed, "#buttons #random")
    def handle_random(self, _: Button.Pressed) -> None:
        self.action_random_respond()

    @on(Button.Pressed, "#buttons #not-last")
    def handle_not_last(self, _: Button.Pressed) -> None:
        self.action_random_not_last_respond()

    @on(Resize)
    def _reflow_log(self, _: Resize) -> None:
        # TODO: This might be a bit heavy with hundreds of messages
        if self.rendered_messages:
            log: RichLog = self.query_one("#messages", RichLog)
            log.clear()
            for msg in self.rendered_messages:
                log.write(msg, shrink=False)

    def action_agent_1_respond(self):
        if self._disable_bindings.is_set():
            return
        self.action_agent_respond(0)

    def action_agent_2_respond(self):
        if self._disable_bindings.is_set():
            return
        self.action_agent_respond(1)

    def action_agent_3_respond(self):
        if self._disable_bindings.is_set():
            return
        self.action_agent_respond(2)

    def action_enter_narrate(self) -> None:
        if self._disable_bindings.is_set():
            return

        def on_narrate_done(result: str):
            if result:
                result = result.strip()
                message = ChatMessage.narration("DM", result)
                self.state_machine.add_message(message)
                msg = f"**DM:** {result}"
                self.add_message(msg)
                self._update_label("DM narrated.")

        narrate_screen = NarrationScreen(
            title="Narrate",
            transcriber=self.transcriber,
            messages=self.state_machine.messages,
        )
        self.app.push_screen(narrate_screen, on_narrate_done)

    def action_agent_respond(self, index: int) -> None:
        self.agent_respond_async(index)

    @work(exclusive=True, group="agent", exit_on_error=False)
    async def agent_respond_async(self, number: int):
        name = self.agent_names[number]
        self._disable_responses()
        self._update_label(f"{name} is thinking...")
        self.app.notify(f"{name} is thinking")
        try:
            msg = await asyncio.to_thread(self.state_machine.agent_respond, number)
        except Exception as e:
            self._update_label(f"{name} failed to respond: {e}")
            self._enable_responses()
            self.app.notify(f"{name} failed to respond", severity="error")
            return

        text = f"**{msg.author}:** {msg.content}"
        self.add_message(text)

        speak_switch: Switch = self.query_one("#speak-switch")
        should_speak: bool = speak_switch.value

        if should_speak:
            self._update_label(f"{name} is speaking...")
            self.app.notify(f"{name} is speaking...")

            await asyncio.to_thread(self.state_machine.play_message, msg)

        self._update_label(f"{name} responded.")
        self._enable_responses()

    def action_random_respond(self) -> None:
        if self._disable_bindings.is_set():
            return
        i = self.random.randint(0, len(self.agent_names) - 1)
        self.action_agent_respond(i)

    def action_random_not_last_respond(self) -> None:
        if self._disable_bindings.is_set():
            return
        if len(self.agent_names) <= 1:
            return
        last_msg: Optional[ChatMessage] = self.state_machine.get_last_message(["DM"])
        if not last_msg:
            return self.action_random_respond()
        if last_msg.author not in self.agent_names:
            self.app.notify(f"Unknown agent: {last_msg.author}", severity="error")
            return self.action_random_respond()
        bad_index = self.agent_names.index(last_msg.author)
        index = bad_index
        while index == bad_index:
            index = self.random.randint(0, len(self.agent_names) - 1)
        self.action_agent_respond(index)

    def add_message(self, text: str) -> None:
        log: RichLog = self.query_one("#messages", RichLog)
        md = Markdown(text)
        log.write(md, shrink=False)
        self.rendered_messages.append(md)

    def _update_label(self, text: str) -> None:
        self.query_one("#status").update(text)

    def _disable_responses(self) -> None:
        self._toggle_responses(True)

    def _enable_responses(self) -> None:
        self._toggle_responses(False)

    def _toggle_responses(self, disabled: bool) -> None:
        if disabled:
            self._disable_bindings.set()
        else:
            self._disable_bindings.clear()
        for btn in self.query("#buttons .agent"):
            btn.disabled = disabled
        self.query_one("#buttons #narrate").disabled = disabled
        self.query_one("#buttons #random").disabled = disabled
        self.query_one("#buttons #not-last").disabled = disabled


class MainApp(App):
    TITLE = "RPG Party"

    def on_ready(self) -> None:
        logger = logging.getLogger(__name__)
        config_path: Path = Path("config.json")
        if config_path.exists() and config_path.is_file():
            logger.info(f"Loading from {config_path}")
            config: Config = Config.from_path(config_path)
            agents: List[Agent] = []
            # TODO: Make this neater
            openai: OpenAI = _get_openai(config)
            for agent_conf in config.agents:
                agent = agent_conf.create_agent(config.prompt_config, openai=openai)
                agents.append(agent)

            voice_actors: VoiceActorManager = VoiceActorManager()
            for actor_config in config.voice_actors:
                actor: VoiceActor = actor_config.create_actor()
                voice_actors.register_actor(actor)

            messages_path: Optional[Path] = config.messages_path
            self.state_machine: StateMachine = StateMachine(
                agents, voice_actors, messages_file=messages_path
            )
        else:
            logger.info(f"Falling back to non config, create file at {config_path}")
            self.state_machine: StateMachine = _create_old_state_machine()

        if len(self.state_machine.messages) <= 0:
            # Add a message with the player names so everyone knows who is present
            intro_players_msg = ChatMessage.narration(
                "DM",
                "The following player characters are present:\n- "
                + "\n- ".join(self.state_machine.agent_names),
            )
            self.state_machine.add_message(intro_players_msg)

        transcriber: AudioTranscriber = OpenAIAudioTranscriber(openai)
        standby = Standby(self.state_machine, transcriber)
        self.install_screen(standby, "standby")
        self.push_screen("standby")


def _get_openai(config: Config) -> OpenAI:
    api_keys = config.api_keys
    if api_keys:
        return api_keys.get_openai_client()
    else:
        openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        return OpenAI(api_key=openai_api_key)


def _create_old_state_machine() -> StateMachine:
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("No OPENAI_API_KEY defined")
    openai = OpenAI(api_key=openai_api_key)

    prefix_path = "prompts/prefix.md"
    suffix_path = "prompts/suffix.md"
    agents: List[Agent] = [
        OpenAIAgent.load_prompt(
            "Vex",
            "prompts/vex.md",
            openai,
            model="gpt-5-mini",
            prefix_path=prefix_path,
            suffix_path=suffix_path,
        ),
        OpenAIAgent.load_prompt(
            "Garry",
            "prompts/garry.md",
            openai,
            model="gpt-5-mini",
            prefix_path=prefix_path,
            suffix_path=suffix_path,
        ),
        OpenAIAgent.load_prompt(
            "Bleb",
            "prompts/bleb.md",
            openai,
            model="gpt-5-mini",
            prefix_path=prefix_path,
            suffix_path=suffix_path,
        ),
    ]
    voice_actors: VoiceActorManager = VoiceActorManager()
    garry_actor = PiperVoiceActor(["Garry"], "piper-models/en_US-lessac-medium.onnx")
    voice_actors.register_actor(garry_actor)
    other_actor = PiperVoiceActor(
        ["Vex", "Bleb"], "piper-models/en_US-libritts-high.onnx"
    )
    other_actor.set_speaker_id_for("Vex", 14)
    other_actor.set_speaker_id_for("Bleb", 20)
    voice_actors.register_actor(other_actor)

    messages_path: Optional[Path] = None
    messages_path = os.getenv("MESSAGES_PATH")
    if messages_path:
        messages_path = Path(messages_path)

    return StateMachine(agents, voice_actors, messages_file=messages_path)


def setup_logging(level: int = logging.INFO, logfile: str | None = None) -> None:
    handlers: List[logging.Handler] = [TextualHandler()]
    if logfile:
        file_handler = RotatingFileHandler(
            logfile, maxBytes=10_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        handlers.append(file_handler)
    logging.basicConfig(level=level, handlers=handlers, force=True)
    logging.captureWarnings(True)


if __name__ == "__main__":
    load_dotenv()
    setup_logging()
    app = MainApp()
    app.run()
