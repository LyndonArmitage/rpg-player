# AGENTS.md

This repository contains a Python 3.13+ project that implements a simple
application for playing a traditional tabletop roleplaying game with 3 large
language model driven AI characters.

The user take the place of the Dungeon Master (DM), with LLM driven characters
responding to their narration.

It implements this primarily as a TUI application built using the `textual`
library.

## Project Structure & Organisation

The project is managed by the `uv` tool. All Python related command should
generally go through this tool.

There exists additional documentation in the `docs/` folder, which contains
more detailed information on topics such as testing, upgrading, and the
structure of the code.

At a more general level, the project contains a `src/` directory containing the
code for this project. Specifically under `src/rpg_player/`.

Tests are stored in the `tests/` directory and use the `pytest` library.

There also exists a `scripts/` directory for useful scripts and experiments.

The `prompts/` directory contains agent prompt fragments. These are combined
and templated in the source code.

Configuration for the system can exist as JSON or TOML. Examples can be seen in
`config.json` and `config.toml`.

Both source code and test code should be type safe according to `basedpyright`,
formatted according to `black`, and contain no errors detectable by `ruff`.
This can be done using commands prefixed with `uv run`. For more information
see `docs/code-quality.md`.

## Build, Test, and Develop Command Cheat Sheet

Below is a quick cheat sheet of useful commands:

- `uv sync --all-groups` - Installs production and development dependencies
- `uv run python -m rpg_player.app` - Runs the actual application
- `uv run ruff check src/` - Checks the `src/` directory with `ruff`
- `uv run basedpyright src/` - Checks the `src/` directory with `basedpyright`
- `uv run black src/rpg_player/config.py` - Formats `src/rpg_player/config.py`
  with the `black` formatter
- `uv run pytest` - Runs all the tests
