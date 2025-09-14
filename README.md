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

I have built this project using Python 3.13.5 and the
[uv](https://docs.astral.sh/uv/) tool, although it should run with any Python
virtual environment.

You should install/sync dependencies with:

```sh
uv sync --all-groups
```

You can then run this project with:

```sh
uv run python app.py
# Or if you are in the virtual environment:
python app.py
```

Or use textual:

```sh
uv run textual run app.py
# add --dev to allow you to run with debugging like so:
uv run textual console
uv run textual run --dev app.py
```

**Note:** When running with `textual`, you will not be able to provide
arguments as you can with the python command.

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

See `config.py` for the configuration code data classes that are read from the
JSON `config.json` file. Below is a simple example `config.json`:

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

Note that only 3 agents are currently supported in the UI. In the above
example:

- A prefix and suffix prompt have been specified, these will be used by all
  agents
- The path to the messages file where game state will be stored has been set
- 3 agents have been specified with their specific names, prompts, type and
  arguments provided
- 2 voice actor instances have been configured, 1 for the speaker "Garry", and
  another for both "Vex" and "Bleb"
- Both voice actor instances are using the Piper TTS type but different models
- The OpenAI API Key has been provided via an environment variable

You can also use [TOML](https://toml.io/) instead of JSON if you prefer, but
you will have to set the configuration file with the `--config` argument, e.g.
`--config example.toml`.

## Building

As mentioned above, I built this project using `uv` but you should be able to
use any Python virtual environment.

A `requirements.txt` is automatically generated with:

```sh
uv export --frozen --output-file=requirements.txt
```

This file will only be used if you aren't using `uv`, e.g. using `venv` and
`pip`.

To run the tests you will need to download the `piper-tts` model
`en_US-lessac-medium`. Below is an example of how to do this:

```sh
mkdir piper-models
cd piper-models
uv run python -m piper.download_voices en_US-lessac-medium
```

For more documentation, see the [docs/](docs/) folder. Specifically
[docs/structure.md](/docs/structure.md).
