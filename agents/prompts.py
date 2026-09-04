"""Load per-agent prompts from XML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template
from xml.etree import ElementTree as ET


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return (element.text or "").strip()


class PromptSet:
    """Parsed prompt file for one agent."""

    def __init__(self, root: ET.Element) -> None:
        self._root = root

    def _find(self, tag: str, prompt_id: str) -> ET.Element:
        for child in self._root:
            if child.tag == tag and child.get("id") == prompt_id:
                return child
        raise KeyError(f"Prompt {tag} id={prompt_id!r} not found")

    def text(self, prompt_id: str, **kwargs: object) -> str:
        value = _text(self._find("text", prompt_id))
        return Template(value).safe_substitute(kwargs) if kwargs else value

    def items(self, prompt_id: str) -> list[str]:
        return [_text(item) for item in self._find("list", prompt_id).findall("item") if _text(item)]

    def mapping(self, prompt_id: str) -> dict[str, str]:
        return {
            str(item.get("key")): _text(item)
            for item in self._find("map", prompt_id).findall("item")
            if item.get("key")
        }

    def system(self, prompt_id: str, **kwargs: object) -> str:
        value = _text(self._find("prompt", prompt_id).find("system"))
        return Template(value).safe_substitute(kwargs) if kwargs else value

    def user(self, prompt_id: str, **kwargs: object) -> str:
        value = _text(self._find("prompt", prompt_id).find("user"))
        return Template(value).safe_substitute(kwargs) if kwargs else value


@lru_cache(maxsize=8)
def load_prompts(path: str | Path) -> PromptSet:
    tree = ET.parse(Path(path))
    return PromptSet(tree.getroot())
