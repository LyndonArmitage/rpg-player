"""
This code is used for summarising a sessions worth of messages as a few
different shorter messages:

1. A general summary of all the messages and what happened
2. A personal summary from the perspective of each agent
3. A running summary out of all the previous general summary
"""

import argparse
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import NamedTuple, cast

from dotenv import load_dotenv
from openai import OpenAI

from rpg_player.domain.chat_message import (
    ChatMessage,
    ChatMessages,
    MessageType,
    load_messages_from_file,
)
from rpg_player.domain.token_counter import TokenCounter
from rpg_player.token_counter import TiktokenTokenCounter

log = logging.getLogger(__name__)


SESSION_SUMMARY_PROMPT = """
Messages following these instructions are transcripts of a role-playing game
sessions.

It is your job to reply with a summary of what happened in each session.

- Make sure to mention that this is a summary of the last session
- Keep your summary concise
- Try to keep events in order
- Use bullet point lists where appropriate
- Keep track of NPCs encountered
- Keep track of the actions players took and their outcomes
- Keep track of any items aquired, used or lost
- Keep track of story and quest threads and their progression
- Do not embelish or fabricate events that did not happen
- Only provide the summary, do not offer to provide any other output

The transcripts will be in the format of:

> Player:
> Player narration
> ---
> DM:
> Dungeon Master narration
> ---

That format is the player or DM speaking followed by a colon and new line.
With each message being seperated by `---` followed by a new line.
"""

RUNNING_SUMMARY_PROMPT = """
Messages following these instructions are generated summaries of a
role-playing game sessions.

It is your job to reply with a running summary of what has happened overall.

- Make sure to mention that this is what has happened so far in the adventure
- Keep your summary concise, a few short paragraphs should be enough
- Be descriptive
- Keep events in order
- Focus on the overall quest as well as recent events
- Do not embelish or fabricate events that did not happen

The session summaries will be split by `---` followed by a new line.

"""


class Summaries(NamedTuple):
    last_session: str
    overall: str


def main():
    _ = load_dotenv()
    parser = argparse.ArgumentParser(
        prog="summarise_session",
        description=(
            "Given messages from a session, generate summaries for "
            "the agents and session as a whole."
        ),
    )

    _ = parser.add_argument(
        "input_path",
        help=(
            "The path to the input messages file.\n"
            "The messages should each be on their own line as JSON objects."
        ),
        type=Path,
    )
    _ = parser.add_argument(
        "output_path",
        help="The path to the output messages file.",
        type=Path,
    )

    _ = parser.add_argument(
        "--model",
        help="The OpenAI model to use.",
        default="gpt-6-luna",
        type=str,
    )

    _ = parser.add_argument(
        "--dryrun",
        help="whether to run as a dryrun or not",
        action="store_true",
    )

    args = parser.parse_args()

    openai_client: OpenAI = _get_openai(args)

    input_path: Path = cast(Path, args.input_path)
    output_path: Path = cast(Path, args.output_path)
    model: str = cast(str, args.model)
    dryrun: bool = cast(bool, args.dryrun)

    # Load the messages
    messages: ChatMessages = _load_messages(input_path, model)

    token_counter: TokenCounter = _get_token_counter(model)
    # Count the tokens so we can evaluate how well we shrink the context
    counted_tokens: int = token_counter.count_sum(messages)
    print(f"Found {counted_tokens} raw tokens")

    # Find existing summaries
    existing_summaries: list[ChatMessage] = list(
        messages.filter_type(MessageType.SUMMARY)
    )

    if dryrun:
        print("Stopping in dryrun mode")
        return
    # TODO: Summaries for specific agents

    summaries: Summaries = generate_summaries(
        openai_client, model, messages, existing_summaries
    )

    combined_summary: str = (
        "## Running Summary\n\n"
        f"{summaries.overall}\n\n"
        "## Last Session Summary\n\n"
        f"{summaries.last_session}"
    )
    print(combined_summary)
    summary_message: ChatMessage = ChatMessage.summary("DM", combined_summary)
    with output_path.open("w", encoding="utf-8") as f:
        _ = f.write(json.dumps(asdict(summary_message)))
        _ = f.write("\n")

    summary_tokens: int = token_counter.count(summary_message)
    print(f"Original token count {counted_tokens} vs summary count {summary_tokens}")


def _get_token_counter(model: str) -> TokenCounter:
    return TiktokenTokenCounter(model)


def summarise_session(client: OpenAI, model: str, messages: ChatMessages) -> str:
    """
    Summarise the session so far, ignoring other summary messages
    """

    # This is going to build a large string when there are a lot of messages
    transcript: str = ""
    delimiter: str = "\n---\n"
    msg_count: int = 0
    for msg in messages.messages:
        if msg.message_type == MessageType.SUMMARY:
            continue
        msg_count += 1
        line: str = format_message(msg) + delimiter
        transcript += line

    if msg_count <= 0:
        raise ValueError("No messages to summarise")
    log.info(f"Summarising transcript of {msg_count} messages")

    summary: str = run_summary(client, model, transcript, SESSION_SUMMARY_PROMPT)
    return summary


def generate_summaries(
    client: OpenAI,
    model: str,
    messages: ChatMessages,
    existing_summaries: list[ChatMessage],
) -> Summaries:
    """
    Summarise the current session as well as create an ongoing summary
    """
    session_summary: str = summarise_session(client, model, messages)
    overall_summary: str = summarise_summaries(
        client, model, existing_summaries, session_summary
    )
    return Summaries(session_summary, overall_summary)


def summarise_summaries(
    client: OpenAI, model: str, existing_summaries: list[ChatMessage], last_session: str
) -> str:
    """
    Take all the previous summaries and the current summary and generate a
    running summary.
    """
    summary_texts: list[str] = [msg.content.strip() for msg in existing_summaries]
    summary_texts.append(last_session)
    text = "\n---\n".join(summary_texts).strip()
    return run_summary(client, model, text, RUNNING_SUMMARY_PROMPT)


def run_summary(client: OpenAI, model: str, text: str, instructions: str) -> str:
    response = client.responses.create(
        input=text,
        instructions=instructions,
        model=model,
    )

    # NOTE: Previously this did a lot of stuff based on the shape of the output
    # If this is still needed we will need to handle it.
    return response.output_text


def format_message(msg: ChatMessage) -> str:
    line: str = f"{msg.author}:\n{msg.content}"
    return line


def _load_messages(path: Path, _model: str) -> ChatMessages:
    log.info(f"Loading messages from {path}")
    loaded: list[ChatMessage] = load_messages_from_file(path)
    count: int = len(loaded)
    msgs = ChatMessages()
    msgs.extend(loaded)
    log.info(f"Loaded {count} messages")
    return msgs


def _get_openai(args: argparse.Namespace) -> OpenAI:
    api_key: str | None = os.getenv("OPENAI_API_KEY")
    if not api_key:
        if "openai_api_key" in args:
            api_key = getattr(args, "open_api_key", None)
    if not api_key:
        raise ValueError("Missing OpenAI API Key")
    return OpenAI(api_key=api_key)


if __name__ == "__main__":
    main()
