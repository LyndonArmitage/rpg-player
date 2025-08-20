import asyncio
import logging
import os
from random import Random
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.logging import TextualHandler
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Markdown, Rule

from agent import Agent, OpenAIAgent
from chat_message import ChatMessage
from main import setup_logging
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

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="messages")
        yield Rule(line_style="thick")
        with Horizontal(id="buttons"):
            yield Button("Narrate", id="narrate")
            for i, agent_name in enumerate(self.agent_names):
                btn = Button(f"{i+1}: {agent_name}", id=f"agent{i}", classes="agent")
                btn.data = {"index": i, "name": agent_name}
                yield btn
            yield Button("Random Respond", id="random")
            yield Button("Not Last Respond", id="not-last")
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
        self.action_agent_respond(0)

    def action_agent_2_respond(self):
        self.action_agent_respond(1)

    def action_agent_3_respond(self):
        self.action_agent_respond(2)

    def action_enter_narrate(self) -> None:
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
        self.agent_respond(index)

    def agent_respond(self, number: int):
        # TODO: should probably use self.run_worker() for actual running code
        msg = self.state_machine.agent_respond(number)
        text = f"**{msg.author}:** {msg.content}"
        self.call_after_refresh(lambda: asyncio.create_task(self.add_message(text)))
        self.state_machine.play_message(msg)

    def action_random_respond(self) -> None:
        i = self.random.randint(0, len(self.agent_names) - 1)
        self.action_agent_respond(i)

    def action_random_not_last_respond(self) -> None:
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


if __name__ == "__main__":
    load_dotenv()
    setup_logging()
    logging.getLogger().addHandler(TextualHandler())
    app = MainApp()
    app.run()
