import logging
import os
from typing import Optional

from dotenv import load_dotenv


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # ensures re-running doesn't duplicate handlers
    )
    if path := os.getenv("LOG_FILE"):
        logging.getLogger().addHandler(logging.FileHandler(path))


def main():
    load_dotenv()
    setup_logging()
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    log = logging.getLogger(__name__)
    if not openai_api_key:
        raise ValueError("No OPENAI_API_KEY defined")
    log.info("Hello from rpg-player!")


if __name__ == "__main__":
    main()
