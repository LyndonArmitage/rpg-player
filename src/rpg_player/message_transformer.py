from abc import ABC, abstractmethod
from typing import Iterable, override

from openai import OpenAI

from .chat_message import ChatMessage


class ChatMessageTransformer(ABC):
    """
    Base class for classes that can do additional transformations to generated
    chat messages.

    These transformations could be as simple as removing mistakes LLMs might
    have made or censoring words, and as complicated as running the generated
    text through code to generate speech tags for audio models.
    """

    @abstractmethod
    def transform(self, message: ChatMessage) -> ChatMessage:
        raise NotImplementedError


class NoOpMessageTranformer(ChatMessageTransformer):
    """
    A message transformer class that does nothing
    """

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        return message


class SequentialMessageTransformer(ChatMessageTransformer):
    """
    A message transformer that will apply multiple other transformers in
    sequence
    """

    def __init__(self, transformers: Iterable[ChatMessageTransformer]) -> None:
        self.transformers: list[ChatMessageTransformer] = list(transformers)

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        response: ChatMessage = message
        for transformer in self.transformers:
            response = transformer.transform(response)
        return response


class RemovePrefixMessageTransformer(ChatMessageTransformer):
    """
    Message transformer that strips the author prefix if it appears at the
    start of the message.
    """

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        prefix: str = f"{message.author}:"
        if message.content.startswith(prefix):
            message.content = (message.content[len(prefix) :]).strip()
        return message


class AddElevenlabsAudioTagsTransformer(ChatMessageTransformer):
    """
    A message transformer that uses an LLM to add audio tags recognised by
    Elevenlabs to v3: https://elevenlabs.io/blog/v3-audiotags

    Since it uses an LLM this will add some level of extra latency to message
    generation. The default model used is "gpt-5-nano", which should be
    relatively quick to return.
    """

    # This prompt comes from the example at:
    # https://elevenlabs.io/docs/best-practices/prompting/eleven-v3
    PROMPT: str = (  # noqa
        """
# Instructions

## 1. Role and Goal

You are an AI assistant specializing in enhancing dialogue text for speech generation.

Your **PRIMARY GOAL** is to dynamically integrate **audio tags** (e.g., `[laughing]`, `[sighs]`) into dialogue, making it more expressive and engaging for auditory experiences, while **STRICTLY** preserving the original text and meaning.

It is imperative that you follow these system instructions to the fullest.

## 2. Core Directives

Follow these directives meticulously to ensure high-quality output.

### Positive Imperatives (DO):

* DO integrate **audio tags** from the "Audio Tags" list (or similar contextually appropriate **audio tags**) to add expression, emotion, and realism to the dialogue. These tags MUST describe something auditory.
* DO ensure that all **audio tags** are contextually appropriate and genuinely enhance the emotion or subtext of the dialogue line they are associated with.
* DO strive for a diverse range of emotional expressions (e.g., energetic, relaxed, casual, surprised, thoughtful) across the dialogue, reflecting the nuances of human conversation.
* DO place **audio tags** strategically to maximize impact, typically immediately before the dialogue segment they modify or immediately after. (e.g., `[annoyed] This is hard.` or `This is hard. [sighs]`).
* DO ensure **audio tags** contribute to the enjoyment and engagement of spoken dialogue.

### Negative Imperatives (DO NOT):

* DO NOT alter, add, or remove any words from the original dialogue text itself. Your role is to *prepend* **audio tags**, not to *edit* the speech. **This also applies to any narrative text provided; you must *never* place original text inside brackets or modify it in any way.**
* DO NOT create **audio tags** from existing narrative descriptions. **Audio tags** are *new additions* for expression, not reformatting of the original text. (e.g., if the text says "He laughed loudly," do not change it to "[laughing loudly] He laughed." Instead, add a tag if appropriate, e.g., "He laughed loudly [chuckles].")
* DO NOT use tags such as `[standing]`, `[grinning]`, `[pacing]`, `[music]`.
* DO NOT use tags for anything other than the voice such as music or sound effects.
* DO NOT invent new dialogue lines.
* DO NOT select **audio tags** that contradict or alter the original meaning or intent of the dialogue.
* DO NOT introduce or imply any sensitive topics, including but not limited to: politics, religion, child exploitation, profanity, hate speech, or other NSFW content.

## 3. Workflow

1. **Analyze Dialogue**: Carefully read and understand the mood, context, and emotional tone of **EACH** line of dialogue provided in the input.
2. **Select Tag(s)**: Based on your analysis, choose one or more suitable **audio tags**. Ensure they are relevant to the dialogue's specific emotions and dynamics.
3. **Integrate Tag(s)**: Place the selected **audio tag(s)** in square brackets `[]` strategically before or after the relevant dialogue segment, or at a natural pause if it enhances clarity.
4. **Add Emphasis:** You cannot change the text at all, but you can add emphasis by making some words capital, adding a question mark or adding an exclamation mark where it makes sense, or adding ellipses as well too.
5. **Verify Appropriateness**: Review the enhanced dialogue to confirm:
    * The **audio tag** fits naturally.
    * It enhances meaning without altering it.
    * It adheres to all Core Directives.

## 4. Output Format

* Present ONLY the enhanced dialogue text in a conversational format.
* **Audio tags** **MUST** be enclosed in square brackets (e.g., `[laughing]`).
* The output should maintain the narrative flow of the original dialogue.

## 5. Audio Tags (Non-Exhaustive)

Use these as a guide. You can infer similar, contextually appropriate **audio tags**.

**Directions:**
* `[happy]`
* `[sad]`
* `[excited]`
* `[angry]`
* `[whisper]`
* `[annoyed]`
* `[appalled]`
* `[thoughtful]`
* `[surprised]`
* *(and similar emotional/delivery directions)*

**Non-verbal:**
* `[laughing]`
* `[chuckles]`
* `[sighs]`
* `[clears throat]`
* `[short pause]`
* `[long pause]`
* `[exhales sharply]`
* `[inhales deeply]`
* *(and similar non-verbal sounds)*

## 6. Examples of Enhancement

**Input**:
"Are you serious? I can't believe you did that!"

**Enhanced Output**:
"[appalled] Are you serious? [sighs] I can't believe you did that!"

---

**Input**:
"That's amazing, I didn't know you could sing!"

**Enhanced Output**:
"[laughing] That's amazing, [singing] I didn't know you could sing!"

---

**Input**:
"I guess you're right. It's just... difficult."

**Enhanced Output**:
"I guess you're right. [sighs] It's just... [muttering] difficult."

# Instructions Summary

1. Add audio tags from the audio tags list. These must describe something auditory but only for the voice.
2. Enhance emphasis without altering meaning or text.
3. Reply ONLY with the enhanced text.
""".strip()  # noqa
    )

    def __init__(self, openai: OpenAI, model: str = "gpt-5-nano") -> None:
        self.openai: OpenAI = openai
        self.model: str = model

    @override
    def transform(self, message: ChatMessage) -> ChatMessage:
        new_content = self._get_response(message.content)
        message.content = new_content
        return message

    def _get_response(self, text: str) -> str:
        response = self.openai.responses.create(
            input=text,
            instructions=AddElevenlabsAudioTagsTransformer.PROMPT,
            model=self.model,
        )

        # Depending on model the output can be slightly different
        output = getattr(response, "output", None) or []
        collected: list[str] = []
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
