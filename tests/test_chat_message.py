import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest

from rpg_player.domain.chat_message import (
    ChatMessage,
    ChatMessages,
    MessageType,
    load_messages_from_file,
)


@pytest.mark.parametrize(
    ("factory", "message_type"),
    [
        (ChatMessage.speech, MessageType.SPEECH),
        (ChatMessage.narration, MessageType.NARRATION),
        (ChatMessage.system, MessageType.SYSTEM),
        (ChatMessage.summary, MessageType.SUMMARY),
    ],
)
def test_message_factories_set_message_fields(
    factory: Callable[[str, str], ChatMessage], message_type: MessageType
):
    message = factory("Alice", "Hello")

    assert message.author == "Alice"
    assert message.content == "Hello"
    assert message.message_type == message_type
    assert message.msg_id


def test_messages_have_different_ids():
    first = ChatMessage.speech("Alice", "One")
    second = ChatMessage.speech("Alice", "Two")

    assert first.msg_id != second.msg_id


def test_message_from_dict_preserves_values():
    message = ChatMessage.from_dict(
        {
            "author": "DM",
            "content": "A new room opens.",
            "message_type": MessageType.NARRATION,
            "msg_id": "message-1",
        }
    )

    assert message == ChatMessage(
        author="DM",
        content="A new room opens.",
        message_type=MessageType.NARRATION,
        msg_id="message-1",
    )


@pytest.mark.parametrize(
    ("message_type", "expected_role"),
    [
        (MessageType.SPEECH, "assistant"),
        (MessageType.NARRATION, "user"),
        (MessageType.SYSTEM, "developer"),
        (MessageType.SUMMARY, "assistant"),
    ],
)
def test_as_openai_msg_maps_message_type_to_role(
    message_type: MessageType, expected_role: str
):
    message = ChatMessage("Alice", "Hello", message_type, "message-1")

    assert message.as_openai_msg() == {
        "role": expected_role,
        "content": "Alice: Hello",
    }


def test_summary_by_dm_is_an_openai_user_message():
    message = ChatMessage.summary("DM", "Previously...")

    assert message.as_openai_msg() == {
        "role": "user",
        "content": "DM: Previously...",
    }


def test_as_openai_msg_uses_custom_system_role():
    message = ChatMessage.system("system", "Follow these rules")

    assert message.as_openai_msg(system_role="system") == {
        "role": "system",
        "content": "system: Follow these rules",
    }


def test_chat_messages_supports_sequence_operations():
    first = ChatMessage.speech("Alice", "One")
    second = ChatMessage.speech("Bob", "Two")
    messages = ChatMessages([first])

    messages.add_message(second)
    messages.insert(0, ChatMessage.narration("DM", "Once upon a time"))
    messages[1] = first
    messages[1:2] = [second]

    assert len(messages) == 3
    assert list(messages)[1:] == [second, second]
    assert messages[-1] == second
    assert messages.last() == second

    del messages[0]
    assert len(messages) == 2
    assert list(messages.filter_type(MessageType.SPEECH)) == [second, second]


def test_chat_messages_rejects_invalid_assignments():
    messages = ChatMessages([ChatMessage.speech("Alice", "Hello")])

    with pytest.raises(TypeError, match="integer assignment"):
        messages[0] = cast(ChatMessage, cast(object, "not a message"))
    with pytest.raises(TypeError, match="slice assignment"):
        messages[:] = cast(
            Iterable[ChatMessage],
            cast(object, ChatMessage.speech("Alice", "Hello")),
        )


def test_messages_property_is_a_copy():
    message = ChatMessage.speech("Alice", "Hello")
    messages = ChatMessages([message])

    copy = messages.messages
    copy.clear()

    assert list(messages) == [message]


def test_load_messages_from_jsonl(tmp_path: Path):
    path = tmp_path / "messages.jsonl"
    messages = [
        ChatMessage.speech("Alice", "Hello"),
        ChatMessage.narration("DM", "The door opens."),
    ]
    _ = path.write_text(
        "".join(json.dumps(asdict(message)) + "\n" for message in messages)
    )

    loaded = load_messages_from_file(path)

    assert loaded == messages


def test_load_messages_from_missing_file_returns_empty_list(tmp_path: Path):
    assert load_messages_from_file(tmp_path / "missing.jsonl") == []
