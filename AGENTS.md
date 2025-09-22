# Repository Guidelines
This guide distills how to contribute effectively to the rpg-player project.

## Project Structure & Module Organization
- `src/rpg_player/` houses the package: `app.py` drives the Textual UI, while modules like `chat_message.py`, voice actor variants, and `config.py` implement agent logic, audio playback, and configuration parsing.
- `tests/` mirrors the package layout with pytest suites (`test_config.py`, `test_piper.py`, etc.).
- `scripts/` contains one-off utilities (voice actor testers, summariser helpers) runnable via `uv run python scripts/<tool>.py`.
- `prompts/` stores agent prompt fragments; `config.json` / `config.toml` provide runnable examples; place local TTS assets under `piper-models/`.

## Build, Test, and Development Commands
- `uv sync --all-groups` — install runtime + dev dependencies (mirrors `pip install -e .[dev]`).
- `uv run python -m rpg_player.app` — launch the default terminal UI; `textual run rpg_player.app:MainApp` works when Textual CLI is available.
- `uv run ruff check src tests` and `uv run black src tests` — lint and format with the project’s pinned configuration.
- `uv run pytest` — execute the entire test suite; append `-k <pattern>` for focused runs.

## Coding Style & Naming Conventions
Python 3.11+ code uses 4-space indentation, 88-character lines (Black + Ruff config), and snake_case modules/functions. Keep classes in CapWords and store Textual widgets in descriptive nouns (e.g., `NarrationScreen`). Run Black and Ruff before committing; isort is configured via Black profile, so `uv run isort src tests` remains idempotent.

## Testing Guidelines
Pytest is configured with `pythonpath = ["src"]`, so import packages as `rpg_player.*`. Name tests `test_<feature>.py` with function-level `test_*` cases. Audio-related tests assume the Piper `en_US-lessac-medium` model lives in `piper-models/`; download via `uv run python -m piper.download_voices en_US-lessac-medium` before running. Add fixtures to `tests/conftest.py` when sharing setup across modules.

## Commit & Pull Request Guidelines
Recent commits use short, sentence-case imperatives ("Fix some issues from ruff", "Move testing scripts to scripts folder"). Follow that style, group related changes per commit, and reference issue IDs inline when applicable. PRs should summarise motivation, list manual/automated test results (`uv run pytest`, linting), and include screenshots or terminal captures when UI behaviour changes. Link configuration or prompt updates to the scenarios they support.

## Configuration & Secrets
Copy `config.json` or create TOML variants for local runs; never commit API keys. Prefer environment variables over checked-in secrets, and add sample paths (e.g., `OPENAI_API_KEY`) to docs if new components require them.
