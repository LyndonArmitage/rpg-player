"""
This code is used for summarising a sessions worth of messages as a few
different shorter messages:

1. A general summary of all the messages and what happened
2. A personal summary from the perspective of each agent
3. A running summary out of all the previous general summary
"""

import argparse
import logging
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from chat_message import ChatMessage, ChatMessages

log = logging.getLogger(__name__)


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

    input_path: Path = args.input_path

    # Load the messages
    messages: ChatMessages = _load_messages(input_path)  # noqa: F841

    # TODO: Find existing summaries


def _load_messages(path: Path) -> ChatMessages:
    log.info(f"Loading messages from {path}")
    loaded: List[ChatMessage] = ChatMessages.load_messages_from_file(path)
    count: int = len(loaded)
    msgs = ChatMessages()
    msgs.extend(loaded)
    log.info(f"Loaded {count} messages")
    return msgs


if __name__ == "__main__":
    main()
