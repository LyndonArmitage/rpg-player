from typing import cast

from _pytest.logging import LogCaptureFixture
from ollama import ChatResponse, Client, Message

from rpg_player.agents.ollama import OllamaAgent
from rpg_player.domain.chat_message import ChatMessage


class FakeClient:
    def __init__(self, response: ChatResponse):
        self.response: ChatResponse = response
        self.calls: list[tuple[str, list[dict[str, str]], bool]] = []

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        stream: bool,
    ) -> ChatResponse:
        self.calls.append((model, messages, stream))
        return self.response


def make_client(response_text: str = "") -> tuple[Client, ChatResponse, FakeClient]:
    response = ChatResponse(message=Message(role="assistant", content=response_text))
    fake_client = FakeClient(response)
    client = cast(Client, cast(object, fake_client))
    return client, response, fake_client


def test_name_system_message_and_configuration_are_set():
    client, _, _ = make_client()

    agent = OllamaAgent(
        client,
        "Gandalf",
        "You are a wise wizard.",
        model="llama3.2",
        max_tokens=800,
    )

    assert agent.name == "Gandalf"
    assert agent.model == "llama3.2"
    assert agent.max_tokens == 800


def test_respond_converts_developer_messages_to_system_messages():
    client, response, fake_client = make_client("The dragon circles overhead.")
    agent = OllamaAgent(client, "DM", "Run the adventure.", model="llama3.2")
    messages = [
        ChatMessage.system("Rules", "Stay in character."),
        ChatMessage.narration("DM", "A dragon appears."),
        ChatMessage.speech("Rogue", "I draw my bow."),
        ChatMessage.summary("DM", "The party is in danger."),
    ]

    result = agent.respond(messages)

    assert result.author == "DM"
    assert result.content == "The dragon circles overhead."
    assert fake_client.calls == [
        (
            "llama3.2",
            [
                {
                    "role": "system",
                    "content": "Run the adventure.\n\nYour name will show up in messages as: DM",
                },
                {"role": "system", "content": "Rules: Stay in character."},
                {"role": "user", "content": "DM: A dragon appears."},
                {"role": "assistant", "content": "Rogue: I draw my bow."},
                {"role": "user", "content": "DM: The party is in danger."},
            ],
            False,
        )
    ]
    assert response.message.content == result.content


def test_respond_returns_empty_speech_and_warns_when_response_has_no_text(
    caplog: LogCaptureFixture,
):
    client, _, _ = make_client("")
    agent = OllamaAgent(client, "DM", "Run the adventure.", model="llama3.2")

    result = agent.respond([])

    assert result.author == "DM"
    assert result.content == ""
    assert "No assistant message in response" in caplog.text
