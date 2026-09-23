from types import SimpleNamespace
from typing import cast

from _pytest.logging import LogCaptureFixture
from openai import OpenAI
from openai.types.responses.response import Response

from rpg_player.agents.openai import OpenAIAgent
from rpg_player.domain.chat_message import ChatMessage


class FakeResponses:
    def __init__(self, response: Response):
        self.response: Response = response
        self.calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []

    def create(self, *, input: list[dict[str, str]], **kwargs: object) -> Response:
        self.calls.append((input, kwargs))
        return self.response


class FakeClient:
    def __init__(self, responses: FakeResponses):
        self.responses: FakeResponses = responses


def make_client(response_text: str = "") -> tuple[OpenAI, Response, FakeResponses]:
    response = cast(
        Response,
        cast(object, SimpleNamespace(output_text=response_text, output=[])),
    )
    responses = FakeResponses(response)
    client = cast(OpenAI, cast(object, FakeClient(responses)))
    return client, response, responses


def test_name_and_system_message_are_configured():
    client, _, _ = make_client()

    agent = OpenAIAgent(client, "Gandalf", "You are a wise wizard.")

    assert agent.name == "Gandalf"
    assert agent.system_prompt == "You are a wise wizard."
    assert agent.model == "gpt-6-luna"
    assert agent.max_tokens == 3000
    assert agent.system_message == {
        "role": "developer",
        "content": (
            "You are a wise wizard.\n\n"
            "Your name will show up in messages as: Gandalf"
        ),
    }
    assert agent.reasoning == {"effort": "low"}


def test_custom_response_configuration_is_set():
    client, _, _ = make_client()

    agent = OpenAIAgent(
        client,
        "Narrator",
        "Describe the scene.",
        model="gpt-5",
        max_output_tokens=800,
        reasoning_effort={"effort": "high"},
        system_role="system",
    )

    assert agent.model == "gpt-5"
    assert agent.max_tokens == 800
    assert agent.reasoning == {"effort": "high"}
    assert agent.system_role == "system"
    assert agent.system_message["role"] == "system"


def test_respond_converts_messages_and_returns_speech():
    client, response, responses = make_client("The dragon circles overhead.")
    agent = OpenAIAgent(client, "DM", "Run the adventure.")
    messages = [
        ChatMessage.system("Rules", "Stay in character."),
        ChatMessage.narration("DM", "A dragon appears."),
        ChatMessage.speech("Rogue", "I draw my bow."),
        ChatMessage.summary("DM", "The party is in danger."),
    ]

    result = agent.respond(messages)

    assert result.author == "DM"
    assert result.content == "The dragon circles overhead."
    assert responses.calls == [
        (
            [
                {
                    "role": "developer",
                    "content": (
                        "Run the adventure.\n\n"
                        "Your name will show up in messages as: DM"
                    ),
                },
                {"role": "developer", "content": "Rules: Stay in character."},
                {"role": "user", "content": "DM: A dragon appears."},
                {"role": "assistant", "content": "Rogue: I draw my bow."},
                {"role": "user", "content": "DM: The party is in danger."},
            ],
            {
                "model": "gpt-6-luna",
                "max_output_tokens": 3000,
                "reasoning": {"effort": "low"},
            },
        )
    ]
    assert response.output_text == result.content


def test_respond_returns_empty_speech_and_warns_when_response_has_no_text(
    caplog: LogCaptureFixture,
):
    client, _, _ = make_client("")
    agent = OpenAIAgent(client, "DM", "Run the adventure.")

    result = agent.respond([])

    assert result.author == "DM"
    assert result.content == ""
    assert "No assistant message in response" in caplog.text
