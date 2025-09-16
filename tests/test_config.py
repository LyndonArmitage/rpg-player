from pathlib import Path

from rpg_player.config import (
    AgentConfig,
    APIKeys,
    Config,
    PromptConfig,
    VoiceActorConfig,
)

TEST_DATA: dict = {
    "prompt_config": {
        "prefix_path": "foo/prefix.txt",
        "suffix_path": "foo/suffix.txt",
    },
    "messages_path": "foo/messages.json",
    "api_keys": {"openai": "testkey"},
    "agents": [
        {
            "name": "Foo",
            "prompt_path": "foo/prompt.txt",
            "type": "openai",
            "args": {"model": "gpt-5"},
        }
    ],
    "voice_actors": [
        {
            "type": "piper",
            "speakers": ["Foo", "Bar"],
            "args": {"speaker_ids": {"Foo": 1, "Bar": 2}},
        }
    ],
}


def test_from_dict():
    config = Config.from_dict(TEST_DATA)

    assert isinstance(config, Config)
    assert isinstance(config.prompt_config, PromptConfig)
    assert config.prompt_config.prefix_path == Path("foo/prefix.txt")
    assert config.prompt_config.suffix_path == Path("foo/suffix.txt")
    assert config.messages_path == Path("foo/messages.json")
    assert isinstance(config.api_keys, APIKeys)
    assert config.api_keys and config.api_keys.openai == "testkey"

    assert len(config.agents) == 1
    agent = config.agents[0]
    assert isinstance(agent, AgentConfig)
    assert agent.name == "Foo"
    assert agent.prompt_path == Path("foo/prompt.txt")
    assert agent.type == "openai"
    assert agent.args == {"model": "gpt-5"}

    assert len(config.voice_actors) == 1
    va = config.voice_actors[0]
    assert isinstance(va, VoiceActorConfig)
    assert va.type == "piper"
    assert va.speakers == ["Foo", "Bar"]
    assert va.args == {"speaker_ids": {"Foo": 1, "Bar": 2}}
