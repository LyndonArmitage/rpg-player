import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class APIKeys:
    openai: Optional[str] = None


@dataclass
class PromptConfig:
    prefix_path: Path
    suffix_path: Path


@dataclass
class AgentConfig:
    name: str
    prompt_path: Path
    model: str
    # TODO: Add deeper AI config


@dataclass
class VoiceActorConfig:
    type: str
    speakers: Dict[str, int]
    args: dict


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
            return APIKeys(openai=d.get("openai"))

        def parse_agent(d: dict) -> AgentConfig:
            return AgentConfig(
                name=d["name"],
                prompt_path=Path(d["prompt_path"]),
                model=d["model"],
            )

        def parse_voice_actor(d: dict) -> VoiceActorConfig:
            return VoiceActorConfig(
                type=d["type"],
                speakers=dict(d.get("speakers", {})),
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
        if path.is_file():
            raise ValueError(f"path is not a file: {path}")
        extension: str = path.suffix.casefold()
        match extension:
            case ".json":
                return Config.from_dict(json.loads(path.read_text()))
            # TODO: Allow for TOML config

        raise ValueError(f"path was not a valid config file: {path}")
