# RPG Player

This is a tool inspired by DougDoug's AI powered RPG Videos:

- https://www.youtube.com/watch?v=-82Ttuy2BtM
- https://www.youtube.com/watch?v=TpYVyJBmH0g

Specifically it is trying to do something similar to his
[Multi-Agent-GPT-Characters
repository](https://github.com/DougDougGithub/Multi-Agent-GPT-Characters).

## Building

I have built this project using Python 3.13.5 and the
[uv](https://docs.astral.sh/uv/) tool, although it should run with any Python
virtual environment.

You should install/sync dependencies with:

```sh
uv sync --all-groups
```

You can then run this project with:

```sh
uv run python main.py
```

A `requirements.txt` is automatically generated with:

```sh
uv export--format=requirements.txt --output-file=requirements.txt
```

This file will only be used if you aren't using `uv`, e.g. using `venv` and
`pip`.

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
them is below:

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
