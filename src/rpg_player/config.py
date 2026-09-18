import json
import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, Unpack

from elevenlabs.client import ElevenLabs
from openai import OpenAI

from rpg_player.agents.openai import OpenAIAgent
from rpg_player.domain.agent import Agent
from rpg_player.domain.voice_actor import VoiceActor
from rpg_player.voice.basic import BasicVoiceActor
from rpg_player.voice.elevenlabs import ElevenlabsVoiceActor
from rpg_player.voice.openai import OpenAIVoiceActor
from rpg_player.voice.piper import PiperVoiceActor

from .prompt_parser import PromptParser


@dataclass
class APIKeys:
    openai: str | None = None
    elevenlabs: str | None = None

    def get_openai_client(self) -> OpenAI:
        """
        Get an OpenAI client from the configuration or environment
        """
        if self.openai:
            return OpenAI(api_key=self.openai)
        else:
            log = logging.getLogger(__name__)
            log.warning("Using OpenAI Key from environment")
            return OpenAI()

    def get_elevenlabs_client(self) -> ElevenLabs:
        """
        Get an Elevenlabs client using the config or environment for the API
        key
        """
        if self.elevenlabs:
            return ElevenLabs(api_key=self.elevenlabs)
        else:
            log = logging.getLogger(__name__)
            log.warning("Using ElevenLabs Key from environment")
            return ElevenLabs()


@dataclass
class PromptConfig:
    prefix_path: Path
    suffix_path: Path


class AgentArgs(TypedDict):
    """ "Configurable agent arguments"""

    model: NotRequired[str]
    max_output_tokens: NotRequired[int]


class OpenAIKwargs(TypedDict):
    """Required arguments for OpenAI Agents"""

    openai: OpenAI


@dataclass
class AgentConfig:
    name: str
    prompt_path: Path
    type: str
    args: AgentArgs

    def create_agent(
        self, prompt_config: PromptConfig, **kwargs: Unpack[OpenAIKwargs]
    ) -> Agent:
        match self.type.casefold():
            case "openai":
                openai: OpenAI = kwargs.get("openai")
                return self.create_openai(openai, prompt_config, **kwargs)
            case _:
                raise NotImplementedError(f"No agent implemented for type {self.type}")

    def create_openai(
        self,
        openai_client: OpenAI,
        prompt_config: PromptConfig,
        **_kwargs: Unpack[AgentArgs],
    ) -> OpenAIAgent:
        model: str = self.args.get("model", "gpt-5.6-luna")
        max_output_tokens: int = self.args.get("max_output_tokens", 3000)
        system_role: Literal["system", "developer"] = self.args.get(
            "system_prompt", "developer"
        )

        prompt_parser = PromptParser({"name": self.name, "model": model})
        prompt_text: str = prompt_parser.parse_prompt_paths(
            self.prompt_path,
            prompt_config.prefix_path,
            prompt_config.suffix_path,
        )

        return OpenAIAgent(
            openai=openai_client,
            name=self.name,
            system_prompt=prompt_text,
            model=model,
            max_output_tokens=max_output_tokens,
            reasoning_effort=None,  # TODO: Make reasoning configurable
            system_role=system_role,
        )


@dataclass
class VoiceActorConfig:
    type: str
    speakers: list[str]
    args: dict

    def create_actor(self, api_keys: APIKeys | None) -> VoiceActor:
        match self.type.casefold():
            case "piper":
                return self._create_piper_actor()
            case "elevenlabs":
                return self._create_elevenlabs_actor(api_keys)
            case "openai":
                return self._create_openai_actor(api_keys)
            case "basic":
                return self._create_basic_actor()
        raise NotImplementedError(f"Not implemented for type: {self.type}")

    def _create_piper_actor(self) -> PiperVoiceActor:
        args: dict = self.args
        model_path: str = args.get("model_path")
        if not model_path:
            raise ValueError("Missing 'model_path' from args")
        actor = PiperVoiceActor(self.speakers, Path(model_path))
        speaker_ids: dict[str, int] = args.get("speaker_ids", {})
        for name, speaker_id in speaker_ids.items():
            actor.set_speaker_id_for(name, speaker_id)
        return actor

    def _create_elevenlabs_actor(
        self, api_keys: APIKeys | None
    ) -> ElevenlabsVoiceActor:
        client: ElevenLabs = None
        if api_keys:
            client = api_keys.get_elevenlabs_client()
        else:
            client = ElevenLabs()
        args: dict = self.args
        voice_id: str | None = args.get("voice_id")
        if not voice_id:
            raise ValueError("Missing 'voice_id' from args")
        model_id: str | None = args.get("model_id")
        if not model_id:
            return ElevenlabsVoiceActor(self.speakers, client, voice_id)
        else:
            return ElevenlabsVoiceActor(
                self.speakers, client, voice_id, model_id=model_id
            )

    def _create_openai_actor(self, api_keys: APIKeys | None) -> OpenAIVoiceActor:
        client: OpenAI = None
        if api_keys:
            client = api_keys.get_openai_client()
        else:
            client = OpenAI()
        args: dict = self.args
        return OpenAIVoiceActor(self.speakers, client, **args)

    def _create_basic_actor(self) -> BasicVoiceActor:
        return BasicVoiceActor(self.speakers)


@dataclass
class Config:
    """
    Main configuration class for the application
    """

    prompt_config: PromptConfig
    messages_path: Path | None = None
    api_keys: APIKeys | None = None
    agents: list[AgentConfig] = field(default_factory=list)
    voice_actors: list[VoiceActorConfig] = field(default_factory=list)
    text_chat_path: Path | None = None

    @staticmethod
    def from_dict(data: dict) -> "Config":
        """
        Load configuration from a dictionary object
        """

        def path_or_none(val) -> Path | None:
            if val is None:
                return None
            return Path(val)

        def parse_prompt_config(d: dict) -> PromptConfig:
            return PromptConfig(
                prefix_path=Path(d["prefix_path"]),
                suffix_path=Path(d["suffix_path"]),
            )

        def parse_api_keys(d: dict) -> APIKeys:
            return APIKeys(openai=d.get("openai"), elevenlabs=d.get("elevenlabs"))

        def parse_agent(d: dict) -> AgentConfig:
            return AgentConfig(
                name=d["name"],
                prompt_path=Path(d["prompt_path"]),
                type=d["type"],
                args=dict(d.get("args", {})),
            )

        def parse_voice_actor(d: dict) -> VoiceActorConfig:
            return VoiceActorConfig(
                type=d["type"],
                speakers=list(d.get("speakers", [])),
                args=dict(d.get("args", {})),
            )

        return Config(
            prompt_config=parse_prompt_config(data["prompt_config"]),
            messages_path=path_or_none(data.get("messages_path")),
            api_keys=(
                parse_api_keys(data["api_keys"])
                if data.get("api_keys") is not None
                else None
            ),
            agents=[parse_agent(agent) for agent in data.get("agents", [])],
            voice_actors=[parse_voice_actor(v) for v in data.get("voice_actors", [])],
            text_chat_path=path_or_none(data.get("text_chat_path")),
        )

    @staticmethod
    def from_path(path: Path | str) -> "Config":
        """
        Load configuration from a given path
        """
        if isinstance(path, str):
            path = Path(str)
        if not path.exists():
            raise ValueError(f"path does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"path is not a file: {path}")
        extension: str = path.suffix.casefold()
        match extension:
            case ".json":
                return Config.from_dict(json.loads(path.read_text()))
            case ".toml":
                return Config.from_dict(tomllib.loads(path.read_text()))

        raise ValueError(f"path was not a valid config file: {path}")
