import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from elevenlabs.client import ElevenLabs
from openai import OpenAI

from agent import Agent, OpenAIAgent
from elevenlabs_voice_actor import ElevenlabsVoiceActor
from openai_voice_actor import OpenAIVoiceActor
from piper_voice_actor import PiperVoiceActor
from voice_actor import VoiceActor


@dataclass
class APIKeys:
    openai: Optional[str] = None
    elevenlabs: Optional[str] = None

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


@dataclass
class AgentConfig:
    name: str
    prompt_path: Path
    type: str
    args: dict

    def create_agent(self, prompt_config: PromptConfig, **kwargs) -> Agent:
        match self.type.casefold():
            case "openai":
                openai: Optional[OpenAI] = kwargs.get("openai")
                if not openai:
                    raise ValueError("Missing 'openai' parameter")
                if not isinstance(openai, OpenAI):
                    raise ValueError("'openai' is not an OpenAI object")
                return self.create_openai(openai, prompt_config, **kwargs)
        raise NotImplementedError(f"No agent implemented for type {self.type}")

    def create_openai(
        self, openai_client: OpenAI, prompt_config: PromptConfig, **kwargs
    ) -> OpenAIAgent:
        args: dict = {**self.args, **kwargs}
        model: str = args.get("model", "gpt-5-mini")
        return OpenAIAgent.load_prompt(
            self.name,
            self.prompt_path,
            openai_client,
            model=model,
            prefix_path=prompt_config.prefix_path,
            suffix_path=prompt_config.suffix_path,
        )


@dataclass
class VoiceActorConfig:
    type: str
    speakers: List[str]
    args: dict

    def create_actor(self, api_keys: Optional[APIKeys]) -> VoiceActor:
        match self.type.casefold():
            case "piper":
                return self._create_piper_actor()
            case "elevenlabs":
                return self._create_elevenlabs_actor(api_keys)
            case "openai":
                return self._create_openai_actor(api_keys)
        raise NotImplementedError(f"Not implemented for type: {self.type}")

    def _create_piper_actor(self) -> PiperVoiceActor:
        args: dict = self.args
        model_path: str = args.get("model_path")
        if not model_path:
            raise ValueError("Missing 'model_path' from args")
        actor = PiperVoiceActor(self.speakers, Path(model_path))
        speaker_ids: Dict[str, int] = args.get("speaker_ids", {})
        for name, speaker_id in speaker_ids.items():
            actor.set_speaker_id_for(name, speaker_id)
        return actor

    def _create_elevenlabs_actor(
        self, api_keys: Optional[APIKeys]
    ) -> ElevenlabsVoiceActor:
        client: ElevenLabs = None
        if api_keys:
            client = api_keys.get_elevenlabs_client()
        else:
            client = ElevenLabs()
        args: dict = self.args
        voice_id: Optional[str] = args.get("voice_id")
        if not voice_id:
            raise ValueError("Missing 'voice_id' from args")
        model_id: Optional[str] = args.get("model_id")
        if not model_id:
            return ElevenlabsVoiceActor(self.speakers, client, voice_id)
        else:
            return ElevenlabsVoiceActor(
                self.speakers, client, voice_id, model_id=model_id
            )

    def _create_openai_actor(self, api_keys: Optional[APIKeys]) -> OpenAIVoiceActor:
        client: OpenAI = None
        if api_keys:
            client = api_keys.get_openai_client()
        else:
            client = OpenAI()
        args: dict = self.args
        return OpenAIVoiceActor(self.speakers, client, **args)


@dataclass
class Config:
    """
    Main configuration class for the application
    """

    prompt_config: PromptConfig
    messages_path: Optional[Path] = None
    api_keys: Optional[APIKeys] = None
    agents: List[AgentConfig] = field(default_factory=list)
    voice_actors: List[VoiceActorConfig] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict) -> "Config":
        """
        Load configuration from a dictionary object
        """

        def path_or_none(val) -> Optional[Path]:
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
        )

    @staticmethod
    def from_path(path: Union[Path, str]) -> "Config":
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
            # TODO: Allow for TOML config

        raise ValueError(f"path was not a valid config file: {path}")
