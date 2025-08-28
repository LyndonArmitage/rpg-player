# RPG Player

This is a tool inspired by DougDoug's AI powered RPG Videos:

- https://www.youtube.com/watch?v=-82Ttuy2BtM
- https://www.youtube.com/watch?v=TpYVyJBmH0g

Specifically it is trying to do something similar to his
[Multi-Agent-GPT-Characters
repository](https://github.com/DougDougGithub/Multi-Agent-GPT-Characters).

I have a blog post detailing this project:
[lyndon.codes/2025/08/26/toying-with-ai-rpg-party-members/](https://lyndon.codes/2025/08/26/toying-with-ai-rpg-party-members/)

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
```

Or use textual:

```sh
uv run textual run app.py
# add --dev to allow you to run with debugging like so:
uv run textual console
uv run textual run --dev app.py
```

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
configuration file. See `config.py` for the configuration code.

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

## Structure

This system can be viewed as a state machine with the following states:

- standby
- narrate
- response

The `standby` state is the main state that is transitioned to and from the
others. It is where the user decided what to do. They can opt to go into the
`narrate` state, which will let them narrate (either by voice or text) a
message that will be picked up by the AI agents.

From the `standby` state, the user can also request responses from the agents,
which enters the `response` state. The `response` state is where the agents are
asked to respond, which will produce text that is then passed to text-to-speech
components known as Voice Actors.

Generally speaking, this application is supposed to be completely user driven.
The user decides how to proceed in the `standby` state, opting to get a
response from AI Agents or respond themselves.

### Modules

The code has been split into multiple files and classes. Key information on
them follows:

#### ChatMessage and ChatMessages

The `ChatMessage` data class is one of the core classes in the system. It's
a simple container of the chat messages from a use session. These include
system messages, narration and messages from agents.

The `ChatMessages` is essentially a container for `ChatMessage` instances. It
has a convenient API and it also keeps a copy of the messages in an OpenAI
format so that OpenAI based agents don't need to regenerate messages
constantly.

#### VoiceActor and VoiceActorManager

The `VoiceActor` base class is a simple interface for taking a `ChatMessage`
and turning it into speech. Its implementations decide if a given message
should be voice acted by it, and can generate voice acting as a file.

`VoiceActorManager` holds all the instances of `VoiceActor` and is responsible
for calling them all and getting them to generate voice acting. It manages a
temporary folder where the voice acting files should go, and which can be
cleaned up upon exit.

Generally, the voice acting files produced should be cleaned up elsewhere,
after they have been played to avoid storing lots of unneeded files.

You should try to stick with the `WAV` format for output. While it is slightly
larger, it decodes faster, and is supported by more audio systems. Provided
your only a generating a few seconds of audio the size won't be an issue.

The `OpenAIVoiceActor` class uses OpenAI APIs and allows for optional
instructions as part of its input. [OpenAI.fm](https://www.openai.fm/) has
examples of how instructions and voices work together. Sufficed to say, the
instructions can control the general _vibe_ of a voice including tone, dialect,
pronunciation and features. Generally, you should align this with your agent's
prompt for a satisfying voice experience.

#### Agent

The `Agent` base class and its implementations are core to the project, as they
are what will generate response output. Their interface is very simple: given
an instance of `ChatMessages` (the collection), they will produce a single
`ChatMessage` as a response. This `ChatMessage` will not automatically be added
to the `ChatMessages`, but should be passed around for validation and to
generate voice acting.

While the base interface is simple, the setup of the concrete agents is less
so.

For the `OpenAIAgent`, you need to provide it with a client, the model, a name
and a system prompt to use.

The system prompt is probably the most important input of them all as it will
control how the agent responds. You may want to exaggerate characteristics
somewhat in order for them to be more apparent, likewise, you'll want to
indicate how they should speak and request that they limit their output to a
few sentences at most.

#### AudioTranscriber

The `AudioTranscriber` base class defines a standard interface for transcribing
audio files (normally WAV files) and exposes both synchronous and asynchronous
methods for retrieving transcribed text.

Two built-in implementations are provided:

The `OpenAIAudioTranscriber` uses the OpenAI Whisper API to transcribe audio
files. It supports both single-shot and streamed (async handler) transcription,
depending on the Whisper model specified. The constructor allows configuring
the model, language, and additional arguments for the underlying API. When
using the default "whisper-1" model, only the synchronous API is available.
Other models may allow streamed outputs delivered via a callback handler.

### Textual App

The `MainApp`, `Standby` and `NarrationScreen` are all parts of the
[textual](https://textual.textualize.io/) UI framework for Python. This is the
main way this application is used.

`textual` apps are terminal applications. As mentioned earlier, you can run
this using `textual run`. The main application is the `MainApp` class in
`app.py` and makes use of the `Standby` and `NarrationScreen` classes which
embody the two main screen for the app.

### Other Tools

There are multiple other small tools that are built alongside the main
application.

#### Session Summariser

There is a simple session summariser application present in
`summarise_session.py`.

This tool takes in a messages file and outputs a new messages file containing
summaries of the original file. It is designed to shorten the history of passed
to LLMs without losing context.

#### Voice Actor Testing

There are 2 simple `VoiceActor` test apps for manually testing the various
voice acting classes: `actor_tester.py` and `actor_tester2.py`.

`actor_tester.py` is a small `textual` app for testing the audio from
`VoiceActor` instances, specifically Piper TTS based actors. It allows you to
test the various speakers of a single voice if there are multiples associated
with it.

`actor_tester2.py` is a bare bones Python script for testing audio from
implementations. Specifically, it is geared towards making sure both WAV
file playing and streamed audio playing.
