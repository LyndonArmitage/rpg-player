import asyncio
import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from random import Random
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalGroup, VerticalScroll
from textual.logging import TextualHandler
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Markdown, Rule, Switch

from agent import Agent, OpenAIAgent
from chat_message import ChatMessage
from narration_screen import NarrationScreen
from state_machine import StateMachine
from voice_actor import PiperVoiceActor, VoiceActorManager


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

    def __init__(self, state_machine: StateMachine):
        super().__init__()
        self.state_machine: StateMachine = state_machine
        self.agent_names = state_machine.agent_names
        self.random: Random = Random()
        self._disable_bindings = threading.Event()

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="messages")
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
                self.call_after_refresh(
                    lambda: asyncio.create_task(self.add_message(msg))
                )

        self.app.push_screen(NarrationScreen(title="Narrate"), on_narrate_done)

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
        await self.add_message(text)

        speak_switch: Switch = self.query_one("#speak-switch")
        should_speak: bool = speak_switch.value

        if should_speak:
            self._update_label(f"{name} is speaking...")
            self.app.notify(f"{name} is speaking...")

            await asyncio.to_thread(self.state_machine.play_message, msg)

        self._update_label(f"{name} responded.")
        self._enable_responses()

    def _append_markdown(self, text: str) -> None:
        self.call_after_refresh(lambda: asyncio.create_task(self.add_message(text)))

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
        if len(self.state_machine.messages) == 0:
            return self.action_random_respond()
        last_msg: ChatMessage = self.state_machine.messages.last
        if last_msg.author not in self.agent_names:
            return self.action_random_respond()
        bad_index = self.agent_names.index(last_msg.author)
        index = bad_index
        while index == bad_index:
            index = self.random.randint(0, len(self.agent_names) - 1)
        self.action_agent_respond(index)

    async def add_message(self, text: str) -> None:
        log = self.query_one("#messages", VerticalScroll)
        md = Markdown(text, classes="msg")
        await log.mount(md)
        await log.mount(Rule())
        self.call_after_refresh(lambda: log.scroll_end(animate=False))

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
        garry_actor = PiperVoiceActor(
            ["Garry"], "piper-models/en_US-lessac-medium.onnx"
        )
        voice_actors.register_actor(garry_actor)
        other_actor = PiperVoiceActor(
            ["Vex", "Bleb"], "piper-models/en_US-libritts-high.onnx"
        )
        other_actor.set_speaker_id_for("Vex", 14)
        other_actor.set_speaker_id_for("Bleb", 20)
        voice_actors.register_actor(other_actor)
        self.state_machine: StateMachine = StateMachine(agents, voice_actors)

        # Add a message with the player names so everyone knows who is present
        intro_players_msg = ChatMessage.narration(
            "DM",
            "The following player characters are present:\n"
            + "\n- ".join(self.state_machine.agent_names),
        )
        self.state_machine.add_message(intro_players_msg)

        standby = Standby(self.state_machine)
        self.install_screen(standby, "standby")
        self.push_screen("standby")


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
