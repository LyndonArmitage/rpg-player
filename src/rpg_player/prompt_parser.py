from pathlib import Path
from typing import Any, Optional, Union

from jinja2 import Environment, Template


class PromptParser:
    """
    Class for parsing prompts.

    This will template the prompts with whatever variables you pass into it.
    """

    def __init__(self, variables: Optional[dict[str, Any]] = None):
        self.variables: dict[str, Any] = variables if variables is not None else {}
        self.env: Environment = Environment()

    def parse_text(self, text: str) -> str:
        template: Template = self.env.from_string(text)
        return template.render(**self.variables)

    def parse_path(self, path: Union[Path, str]) -> str:
        if not isinstance(path, Path):
            path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        return self.parse_text(path.read_text("utf-8"))

    def parse_prompt_paths(
        self,
        character_path: Path,
        prefix_path: Optional[Union[Path, str]] = None,
        suffix_path: Optional[Union[Path, str]] = None,
    ) -> str:
        char_prompt: str = self.parse_path(character_path)
        total_prompt: str = char_prompt
        if prefix_path:
            prefix: str = self.parse_path(prefix_path)
            total_prompt = prefix + "\n" + char_prompt
        if suffix_path:
            suffix: str = self.parse_path(suffix_path)
            total_prompt = total_prompt + "\n" + suffix
        return total_prompt.strip()
