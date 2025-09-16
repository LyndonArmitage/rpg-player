# RPG Player

A local multi-agent AI RPG tool inspired by DougDoug's AI RPG videos and the
[Multi-Agent-GPT-Characters](https://github.com/DougDougGithub/Multi-Agent-GPT-Characters)
repo.

The videos that inspired this tool are:

- https://www.youtube.com/watch?v=-82Ttuy2BtM
- https://www.youtube.com/watch?v=TpYVyJBmH0g

I have a blog post detailing this project:
[lyndon.codes/2025/08/26/toying-with-ai-rpg-party-members/](https://lyndon.codes/2025/08/26/toying-with-ai-rpg-party-members/)

Below is a simple ASCIICast of the initial application:

[![asciicast](https://asciinema.org/a/DGBLtVsD6PAoNtKv19wQ5SRT6.svg)](https://asciinema.org/a/DGBLtVsD6PAoNtKv19wQ5SRT6)

## Running the App

This project should run in Python versions >= 3.11, but has been built and
tested with Python 3.13.

You should be able to run it with any virtual environment tool (venv, pipx,
poetry, uv, etc.) but it has been build with `uv`. The repository uses a `src/`
layout, so the recommended development workflow is to install the package in
editable mode and use the package module to run the application.

Install dependencies (two options):

- Using `uv`:

```sh
uv sync --all-groups
```

- Using pip / venv (recommended for quick setup):

```sh
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

Run the application:

- After editable install (recommended):

```sh
uv run python -m rpg_player.app
# or with python when in virtual environment:
python -m rpg_player.app
```

- If you prefer to run directly from source without installing, ensure `src/`
is on your PYTHONPATH and run the module:

```sh
PYTHONPATH=src python -m rpg_player.app
```

If you want to run with the Textual runtime, run the same module but use
Textual as appropriate. Example using `uv`:

```sh
# Run using the Textual CLI (recommended when textual is installed).
# After installing editable (or in your virtualenv):
textual run rpg_player.app:MainApp
# Or explicitly via python -m textual:
python -m textual run rpg_player.app:MainApp
# If you prefer to run under uv:
uv run textual run rpg_player.app:MainApp
# add --dev flags according to your Textual setup if required
```

### Piper models

For `piper-tts` models, you can download them like so:

```sh
mkdir piper-models
cd piper-models
uv run python -m piper.download_voices en_US-lessac-medium
uv run python -m piper.download_voices en_US-libritts-high
```

The models mentioned above are the 2 I have tested with.

### Configuration

An example configuration can be seen in the `config.json` file. You should
provide your OpenAI API Key via the environment variable or within this
configuration file. Likewise, for Elevenlabs, you should provide your API key
in the `config.json` or environment variable.

See `src/rpg_player/config.py` for the configuration dataclasses that are read
from the JSON or TOML configuration file. Below is a simple example
`config.json`:

```json
{
  "prompt_config": {
    "prefix_path": "prompts/prefix.md",
    "suffix_path": "prompts/suffix.md"
  },
  "messages_path": "game.log",
  "agents": [
    {
      "name": "Vex",
      "prompt_path": "prompts/vex.md",
      "type": "openai",
      "args": {
        "model": "gpt-5-mini"
      }
    },
    {
      "name": "Garry",
      "prompt_path": "prompts/garry.md",
      "type": "openai",
      "args": {
        "model": "gpt-5-mini"
      }
    },
    {
      "name": "Bleb",
      "prompt_path": "prompts/bleb.md",
      "type": "openai",
      "args": {
        "model": "gpt-5-mini"
      }
    }
  ],
  "voice_actors": [
    {
      "type": "piper",
      "speakers": ["Garry"],
      "args": {
        "model_path": "piper-models/en_US-lessac-medium.onnx"
      }
    },
    {
      "type": "piper",
      "speakers": ["Vex", "Bleb"],
      "args": {
        "model_path": "piper-models/en_US-libritts-high.onnx",
        "speaker_ids": {
          "Vex": 14,
          "Bleb": 20
        }
      }
    }
  ]
}
```

Notes about the configuration example:

- Only three agents are currently supported in the UI.
- A prefix and suffix prompt have been specified; these will be used by all
  agents.
- The path to the messages file where game state will be stored has been set.
- Voice actors are configured with the Piper TTS type and model paths.
- The OpenAI API Key can be provided via environment variable or in the
  configuration file.

You can also use TOML instead of JSON; pass `--config example.toml` to the
application to load a TOML config file.

## Building / Packaging

This project uses `pyproject.toml` with a `src/` layout. To work with the
project during development, install editable with dev extras:

```sh
uv sync --group dev
# or
pip install -e .[dev]
```

A `requirements.txt` is automatically generated with:

```sh
uv export --frozen --output-file=requirements.txt
```

## Running tests

To run the tests you will need to download the `piper-tts` model
`en_US-lessac-medium`. Below is an example of how to do this:

```sh
mkdir piper-models
cd piper-models
uv run python -m piper.download_voices en_US-lessac-medium
```

For more documentation, see the [docs/](docs/) folder. Specifically
[docs/structure.md](/docs/structure.md).
