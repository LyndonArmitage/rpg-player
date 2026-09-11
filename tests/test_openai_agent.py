from types import SimpleNamespace
from typing import cast

import pytest
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
    assert agent.system_message == (
        "You are a wise wizard.\n\n" "Your name will show up in messages as: Gandalf"
    )
    assert agent.response_kwargs == {
        "model": "gpt-4.1",
        "instructions": agent.system_message,
        "tool_choice": "none",
        "stream": False,
        "max_output_tokens": 3000,
    }


def test_extra_kwargs_are_added_to_response_request():
    client, _, _ = make_client()

    agent = OpenAIAgent(
        client,
        "Narrator",
        "Describe the scene.",
        model="gpt-5",
        max_tokens=800,
        extra_kwargs={"temperature": 0.4, "metadata": {"source": "test"}},
    )

    assert agent.response_kwargs["model"] == "gpt-5"
    assert agent.response_kwargs["max_output_tokens"] == 800
    assert agent.response_kwargs["temperature"] == 0.4
    assert agent.response_kwargs["metadata"] == {"source": "test"}


@pytest.mark.parametrize(
    "reserved_key",
    [
        "model",
        "input",
        "instructions",
        "tool_choice",
        "stream",
        "max_output_tokens",
    ],
)
def test_reserved_extra_kwargs_are_rejected(reserved_key: str):
    client, _, _ = make_client()

    with pytest.raises(
        ValueError,
        match=r"extra_kwargs contains reserved keyword\(s\)",
    ):
        _ = OpenAIAgent(
            client,
            "Narrator",
            "Describe the scene.",
            extra_kwargs={reserved_key: "overridden"},
        )


def test_respond_converts_messages_and_returns_speech():
    client, response, responses = make_client("The dragon circles overhead.")
    agent = OpenAIAgent(client, "DM", "Run the adventure.")
    messages = [
        ChatMessage.narration("DM", "A dragon appears."),
        ChatMessage.speech("Rogue", "I draw my bow."),
    ]

    result = agent.respond(messages)

    assert result.author == "DM"
    assert result.content == "The dragon circles overhead."
    assert responses.calls == [
        (
            [
                {"role": "user", "content": "DM: A dragon appears."},
                {"role": "assistant", "content": "Rogue: I draw my bow."},
            ],
            agent.response_kwargs,
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
