import json
import logging
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, Unpack, cast

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
    system_role: NotRequired[Literal["system", "developer"]]


class PiperArgs(TypedDict):
    model_path: str
    speaker_ids: NotRequired[dict[str, int]]


class ElevenlabsArgs(TypedDict):
    voice_id: str
    model_id: NotRequired[str]


class OpenAIVoiceArgs(TypedDict, total=False):
    model: str
    voice: str
    response_format: str
    instructions: str


class OpenAIKwargs(TypedDict):
    """Required arguments for OpenAI Agents"""

    openai: OpenAI


AgentType = Literal["openai"]


@dataclass
class AgentConfig:
    name: str
    prompt_path: Path
    type: AgentType
    args: AgentArgs

    def create_agent(
        self, prompt_config: PromptConfig, **kwargs: Unpack[OpenAIKwargs]
    ) -> Agent:
        match self.type:
            case "openai":
                openai: OpenAI = kwargs.get("openai")
                return self.create_openai(openai, prompt_config, **kwargs)

    def create_openai(
        self,
        openai_client: OpenAI,
        prompt_config: PromptConfig,
        **_kwargs: Unpack[AgentArgs],
    ) -> OpenAIAgent:
        model: str = self.args.get("model", "gpt-6-luna")
        max_output_tokens: int = self.args.get("max_output_tokens", 3000)
        system_role: Literal["system", "developer"] = self.args.get(
            "system_role", "developer"
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


VoiceActorType = Literal["piper", "elevenlabs", "openai", "basic"]


@dataclass
class VoiceActorConfig:
    type: VoiceActorType
    speakers: list[str]
    args: dict[str, object]

    def create_actor(self, api_keys: APIKeys | None) -> VoiceActor:
        match self.type:
            case "piper":
                return self._create_piper_actor()
            case "elevenlabs":
                return self._create_elevenlabs_actor(api_keys)
            case "openai":
                return self._create_openai_actor(api_keys)
            case "basic":
                return self._create_basic_actor()

    def _create_piper_actor(self) -> PiperVoiceActor:
        args = cast(PiperArgs, cast(object, self.args))
        model_path = args.get("model_path")
        if not model_path:
            raise ValueError("Missing 'model_path' from args")
        actor = PiperVoiceActor(self.speakers, Path(model_path))
        speaker_ids = args.get("speaker_ids", {})
        for name, speaker_id in speaker_ids.items():
            actor.set_speaker_id_for(name, speaker_id)
        return actor

    def _create_elevenlabs_actor(
        self, api_keys: APIKeys | None
    ) -> ElevenlabsVoiceActor:
        client = api_keys.get_elevenlabs_client() if api_keys else ElevenLabs()
        args = cast(ElevenlabsArgs, cast(object, self.args))
        voice_id = args.get("voice_id")
        if not voice_id:
            raise ValueError("Missing 'voice_id' from args")
        model_id = args.get("model_id")
        if not model_id:
            return ElevenlabsVoiceActor(self.speakers, client, voice_id)
        else:
            return ElevenlabsVoiceActor(
                self.speakers, client, voice_id, model_id=model_id
            )

    def _create_openai_actor(self, api_keys: APIKeys | None) -> OpenAIVoiceActor:
        client = api_keys.get_openai_client() if api_keys else OpenAI()
        args = cast(OpenAIVoiceArgs, cast(object, self.args))
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
    def from_dict(data: Mapping[str, object]) -> "Config":
        """
        Load configuration from a dictionary object
        """

        def object_mapping(value: object, name: str) -> Mapping[str, object]:
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be an object")
            return cast(Mapping[str, object], value)

        def required_string(value: object, name: str) -> str:
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
            return value

        def path_or_none(val: object, name: str) -> Path | None:
            if val is None:
                return None
            return Path(required_string(val, name))

        def parse_prompt_config(d: Mapping[str, object]) -> PromptConfig:
            return PromptConfig(
                prefix_path=Path(
                    required_string(d.get("prefix_path"), "prompt_config.prefix_path")
                ),
                suffix_path=Path(
                    required_string(d.get("suffix_path"), "prompt_config.suffix_path")
                ),
            )

        def parse_api_keys(d: Mapping[str, object]) -> APIKeys:
            keys: dict[str, str | None] = {}
            for name in ("openai", "elevenlabs"):
                value = d.get(name)
                if value is not None and not isinstance(value, str):
                    raise TypeError(f"api_keys.{name} must be a string")
                keys[name] = value
            return APIKeys(**keys)

        def parse_agent_type(value: object) -> AgentType:
            value = required_string(value, "agents.type").casefold()
            if value != "openai":
                raise ValueError(f"Unsupported agent type: {value}")
            return value

        def parse_voice_actor_type(value: object) -> VoiceActorType:
            value = required_string(value, "voice_actors.type").casefold()
            valid_types = {"piper", "elevenlabs", "openai", "basic"}
            if value not in valid_types:
                raise ValueError(f"Unsupported voice actor type: {value}")
            return cast(VoiceActorType, value)

        def parse_agent(d: Mapping[str, object]) -> AgentConfig:
            args = object_mapping(d.get("args", {}), "agents.args")
            return AgentConfig(
                name=required_string(d.get("name"), "agents.name"),
                prompt_path=Path(
                    required_string(d.get("prompt_path"), "agents.prompt_path")
                ),
                type=parse_agent_type(d.get("type")),
                args=cast(AgentArgs, cast(object, dict(args))),
            )

        def parse_voice_actor(d: Mapping[str, object]) -> VoiceActorConfig:
            raw_speakers = d.get("speakers", [])
            if not isinstance(raw_speakers, list):
                raise TypeError("voice_actors.speakers must be a list of strings")
            speakers = cast(list[object], raw_speakers)
            if not all(isinstance(speaker, str) for speaker in speakers):
                raise TypeError("voice_actors.speakers must be a list of strings")
            args = object_mapping(d.get("args", {}), "voice_actors.args")
            return VoiceActorConfig(
                type=parse_voice_actor_type(d.get("type")),
                speakers=cast(list[str], speakers),
                args=dict(args),
            )

        prompt_config = object_mapping(data.get("prompt_config"), "prompt_config")
        api_keys = data.get("api_keys")
        raw_agents = data.get("agents", [])
        raw_voice_actors = data.get("voice_actors", [])
        if not isinstance(raw_agents, list):
            raise TypeError("agents must be a list")
        if not isinstance(raw_voice_actors, list):
            raise TypeError("voice_actors must be a list")
        raw_agents = cast(list[object], raw_agents)
        raw_voice_actors = cast(list[object], raw_voice_actors)

        return Config(
            prompt_config=parse_prompt_config(prompt_config),
            messages_path=path_or_none(data.get("messages_path"), "messages_path"),
            api_keys=(
                parse_api_keys(object_mapping(api_keys, "api_keys"))
                if api_keys is not None
                else None
            ),
            agents=[
                parse_agent(object_mapping(agent, "agents[]")) for agent in raw_agents
            ],
            voice_actors=[
                parse_voice_actor(object_mapping(actor, "voice_actors[]"))
                for actor in raw_voice_actors
            ],
            text_chat_path=path_or_none(data.get("text_chat_path"), "text_chat_path"),
        )

    @staticmethod
    def from_path(path: Path | str) -> "Config":
        """
        Load configuration from a given path
        """
        if isinstance(path, str):
            path = Path(path)
        if not path.exists():
            raise ValueError(f"path does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"path is not a file: {path}")
        extension: str = path.suffix.casefold()
        match extension:
            case ".json":
                return Config.from_dict(
                    cast(dict[str, object], json.loads(path.read_text()))
                )
            case ".toml":
                return Config.from_dict(tomllib.loads(path.read_text()))
            case _:
                pass
        raise ValueError(f"path was not a valid config file: {path}")
