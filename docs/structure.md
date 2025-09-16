# Structure

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

## Modules

The code has been split into multiple files and classes. Key information on
them follows:

### ChatMessage and ChatMessages

The `ChatMessage` data class is one of the core classes in the system. It's
a simple container of the chat messages from a use session. These include
system messages, narration and messages from agents.

The `ChatMessages` is essentially a container for `ChatMessage` instances. It
has a convenient API and it also keeps a copy of the messages in an OpenAI
format so that OpenAI based agents don't need to regenerate messages
constantly.

### VoiceActor and VoiceActorManager

The `VoiceActor` base class is a simple interface for taking a `ChatMessage`
and turning it into speech. Its implementations decide if a given message
should be voice acted by it, and can generate voice acting as a file or stream
it out as soon as it starts being generated.

`VoiceActorManager` holds all the instances of `VoiceActor` and is responsible
for calling them all and getting them to generate voice acting. It manages a
temporary folder where the voice acting files should end up if they don't
support streaming. This folder should be managed by the manager class and be
cleaned up by it to avoid filling storage with audio files.

You should try to stick with the `WAV` format for output when not streaming out
directly to your sound device. While it is slightly larger, it decodes faster,
and is supported by more audio systems. Provided you are only a generating a
few seconds of audio the size won't be an issue.

The `OpenAIVoiceActor` class uses OpenAI APIs and allows for optional
instructions as part of its input. [OpenAI.fm](https://www.openai.fm/) has
examples of how instructions and voices work together. Sufficed to say, the
instructions can control the general _vibe_ of a voice including tone, dialect,
pronunciation and features. Generally, you should align this with your agent's
prompt for a satisfying voice experience. `OpenAIVoiceActor` supports streaming
audio, avoiding the need for storing intermediate files.

The `PiperVoiceActor` class uses Piper TTS and local models to generate voice
lines without going out to the internet. This can mean lower-latency responses,
although it depends on your computer. Quality of Piper models varies widely.
There's a great website with samples of various models at
[rhasspy.github.io/piper-samples](https://rhasspy.github.io/piper-samples/).
Some models feature multiple speakers, allowing you to load a single model and
have a single `VoiceActor` class represent multiple speakers. `PiperVoiceActor`
supports streaming audio for slightly lower-latency and non-storage of
intermediate voice files.

The `ElevenlabsVoiceActor` class uses [ElevenLabs](https://elevenlabs.io/)
online TTS models to generate excellent audio quickly. You'll need to provide
an API key to use them, along with the `voice_id` and possibly `model_id`
(default is their flash model). This class also supports streaming for low
latency responses.

The `BasicVoiceActor` class uses the `pyttsx3` library to generate local speech
using your systems installed text-to-speech APIs. It's likely the fastest voice
actor implementation you can use, but the voice will be robotic. This could be
useful for a robotic character or for simple testing. Like others, this class
supports streaming output for lightening fast audio responses. As a point of
interest, the way `BasicVoiceActor` streams audio may not block in the same way
as other `VoiceActor` implementations.

As you can see, the majority of `VoiceActor` implementations support
streaming output. The option for using intermediate files remains so that it is
easier to implement new `VoiceActor` types in the future.

### Agent

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

### AudioTranscriber

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

The `DummyAudioTranscriber` is a mock `AudioTranscriber` implementation that
will always output text from the `dummy_text` it is given. This is only used
for testing.

## Textual App

The `MainApp`, `Standby` and `NarrationScreen` are all parts of the
[textual](https://textual.textualize.io/) UI framework for Python. This is the
main way this application is used.

`textual` apps are terminal applications. As mentioned earlier, you can run
this using `textual run`. The main application is the `MainApp` class in
`app.py` and makes use of the `Standby` and `NarrationScreen` classes which
embody the two main screen for the app.

## Other Tools

There are multiple other small tools that are built alongside the main
application and bundled in the `scripts/` directory. These can be run using
something like:

```sh
uv run python scripts/piper_actor_tester.py
# obviously replace with appropriate file name
```

### Session Summariser

There is a simple session summariser application present in
`summarise_session.py`.

This tool takes in a messages file and outputs a new messages file containing
summaries of the original file. It is designed to shorten the history passed to
LLMs without losing context.

Currently, only a shared session summary is provided to the agents. In the
future this could be expanded to agent specific summaries to allows for more
specific details to be retained by each agent.

### Voice Actor Testing

There are many simple `VoiceActor` test apps for manually testing the various
voice acting classes.

`actor_tester.py` is a small `textual` app for testing the audio from
`VoiceActor` instances, specifically Piper TTS based actors. It allows you to
test the various speakers of a single voice if there are multiples associated
with it.

There are multiple simple scripts suffixed with `_actor_tester.py` or
`_actor_test.py`. These are bare bones Python script for testing audio from the
various TTS implementation. Specifically, they are geared towards making sure
both WAV file playing and streamed audio playing works. Generally, I use these
for testing output of various models without resorting to a UI.
