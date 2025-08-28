from pathlib import Path

from config import AgentConfig, APIKeys, Config, PromptConfig, VoiceActorConfig


def test_from_dict():
    data = {
        "prompt_config": {
            "prefix_path": "foo/prefix.txt",
            "suffix_path": "foo/suffix.txt",
        },
        "messages_path": "foo/messages.json",
        "api_keys": {"openai": "testkey"},
        "agents": [{"name": "gpt", "prompt_path": "foo/prompt.txt", "model": "gpt-4"}],
        "voice_actors": [
            {"type": "tortoise", "speakers": {"a": 1}, "args": {"foo": "bar"}}
        ],
    }
    config = Config.from_dict(data)

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
    assert agent.name == "gpt"
    assert agent.prompt_path == Path("foo/prompt.txt")
    assert agent.model == "gpt-4"

    assert len(config.voice_actors) == 1
    va = config.voice_actors[0]
    assert isinstance(va, VoiceActorConfig)
    assert va.type == "tortoise"
    assert va.speakers == {"a": 1}
    assert va.args == {"foo": "bar"}
