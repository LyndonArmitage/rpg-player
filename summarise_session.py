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
from pathlib import Path
from typing import List, NamedTuple, Optional

from dotenv import load_dotenv
from openai import OpenAI

from chat_message import ChatMessage, ChatMessages, MessageType

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
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="summarise_session",
        description=(
            "Given messages from a session, generate summaries for "
            "the agents and session as a whole."
        ),
    )

    parser.add_argument(
        "input_path",
        help=(
            "The path to the input messages file.\n"
            "The messages should each be on their own line as JSON objects."
        ),
        type=Path,
    )
    parser.add_argument(
        "output_path",
        help="The path to the output messages file.",
        type=Path,
    )
    parser.add_argument(
        "--config",
        help="The path to an optional config file for more precise configuration",
        required=False,
        dest="config_path",
        type=Path,
    )

    args = parser.parse_args()

    openai_client: OpenAI = _get_openai(args)

    input_path: Path = args.input_path
    output_path: Path = args.output_path

    # Load the messages
    messages: ChatMessages = _load_messages(input_path)

    # Find existing summaries
    existing_summaries: List[ChatMessage] = messages.filter_type(MessageType.SUMMARY)

    # TODO: Summaries for specific agents

    summaries: Summaries = generate_summaries(
        openai_client, messages, existing_summaries
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
        f.write(json.dumps(summary_message.to_dict()))
        f.write("\n")


def summarise_session(client: OpenAI, messages: ChatMessages) -> str:
    """
    Summarise the session so far, ignoring other summary messages
    """

    # This is going to build a large string when there are a lot of messages
    transcript: str = ""
    delimiter: str = "\n---\n"
    msg_count: int = 0
    for msg in messages.messages:
        if msg.type == MessageType.SUMMARY:
            continue
        msg_count += 1
        line: str = format_message(msg) + delimiter
        transcript += line

    if msg_count <= 0:
        raise ValueError("No messages to summarise")
    log.info(f"Summarising transcript of {msg_count} messages")

    summary: str = run_summary(client, transcript, SESSION_SUMMARY_PROMPT)
    return summary


def generate_summaries(
    client: OpenAI, messages: ChatMessages, existing_summaries: List[ChatMessage]
) -> Summaries:
    """
    Summarise the current session as well as create an ongoing summary
    """
    session_summary: str = summarise_session(client, messages)
    overall_summary: str = summarise_summaries(
        client, existing_summaries, session_summary
    )
    return Summaries(session_summary, overall_summary)


def summarise_summaries(
    client: OpenAI, existing_summaries: List[ChatMessage], last_session: str
) -> str:
    """
    Take all the previous summaries and the current summary and generate a
    running summary.
    """
    summary_texts: List[str] = [msg.content.strip() for msg in existing_summaries]
    summary_texts.append(last_session)
    text = "\n---\n".join(summary_texts).strip()
    return run_summary(client, text, RUNNING_SUMMARY_PROMPT)


def run_summary(client: OpenAI, text: str, instructions: str) -> str:

    response = client.responses.create(
        input=text,
        instructions=instructions,
        model="gpt-5-mini",
    )

    # Depending on model the output can be slightly different
    output = getattr(response, "output", None) or []
    collected: List[str] = []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        # item.content is a list of blocks
        for block in getattr(item, "content", []) or []:
            if getattr(block, "type", None) == "output_text":
                txt = getattr(block, "text", "") or ""
                if txt:
                    collected.append(txt)
    if collected:
        return "\n".join(collected).strip()
    # Fallback to output_text
    return (getattr(response, "output_text", "") or "").strip()


def format_message(msg: ChatMessage) -> str:
    line: str = f"{msg.author}:\n{msg.content}"
    return line


def _load_messages(path: Path) -> ChatMessages:
    log.info(f"Loading messages from {path}")
    loaded: List[ChatMessage] = ChatMessages.load_messages_from_file(path)
    count: int = len(loaded)
    msgs = ChatMessages()
    msgs.extend(loaded)
    log.info(f"Loaded {count} messages")
    return msgs


def _get_openai(args: argparse.Namespace) -> OpenAI:
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    if not api_key:
        if "openai_api_key" in args:
            api_key = getattr(args, "open_api_key", None)
    if not api_key:
        raise ValueError("Missing OpenAI API Key")
    return OpenAI(api_key=api_key)


if __name__ == "__main__":
    main()
