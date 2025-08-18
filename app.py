import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Markdown, Rule


class Standby(Screen):

    TITLE = "RPG Party"
    SUB_TITLE = "Standby"
    CSS_PATH = "standby.tcss"
    BINDINGS = [
        ("n", "enter_narrate", "Narrate"),
        ("1", "agent_1_respond", "Agent 1 Respond"),
        ("2", "agent_2_respond", "Agent 2 Respond"),
        ("3", "agent_3_respond", "Agent 3 Respond"),
        ("r", "random_respond", "Random Respond"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="messages")
        yield Rule(line_style="thick")
        yield Horizontal(
            Button("Narrate", id="narrate"),
            Button("Agent 1 Respond", id="agent1"),
            Button("Agent 2 Respond", id="agent2"),
            Button("Agent 3 Respond", id="agent3"),
            Button("Random Respond", id="random"),
            id="buttons",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        id = event.button.id
        match id:
            case "narrate":
                self.action_enter_narrate()
            case "agent1":
                self.action_agent_1_respond()
            case "agent2":
                self.action_agent_2_respond()
            case "agent3":
                self.action_agent_3_respond()
            case "random":
                self.action_random_respond()

    def action_enter_narrate(self) -> None:
        pass

    def action_agent_1_respond(self) -> None:
        self.agent_respond(0)

    def action_agent_2_respond(self) -> None:
        self.agent_respond(1)

    def action_agent_3_respond(self) -> None:
        self.agent_respond(2)

    def agent_respond(self, number: int):
        msg = f"**Player {number}:** Test message."
        self.call_after_refresh(lambda: asyncio.create_task(self.add_message(msg)))

    def action_random_respond(self) -> None:
        self.agent_respond(2)

    async def add_message(self, text: str) -> None:
        log = self.query_one("#messages", VerticalScroll)
        md = Markdown(text, classes="msg")
        await log.mount(md)
        await log.mount(Rule())
        self.call_after_refresh(lambda: log.scroll_end(animate=False))


class MainApp(App):
    TITLE = "RPG Party"

    def on_ready(self) -> None:
        standby = Standby()
        self.install_screen(standby, "standby")
        self.push_screen("standby")


if __name__ == "__main__":
    app = MainApp()
    app.run()
