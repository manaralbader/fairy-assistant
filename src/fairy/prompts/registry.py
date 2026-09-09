"""Prompts are versioned files, never inline strings in Python —
``tests/test_architecture.py`` greps for the shape of a system prompt outside
this registry and fails the build if it finds one. Every version file under
``fairy/prompts/library/<prompt_id>/v*.md`` carries required front matter
(``version``, ``changelog``) checked by :func:`load_prompt`, and the leak
canary is injected into every render automatically — a prompt author cannot
forget to plant it.

A shipped version is never edited in place: a change is a new version file,
so the changelog table in a prompt's directory is also its audit trail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fairy.guardrails.canary import CANARY

LIBRARY_ROOT = Path(__file__).resolve().parent / "library"

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_CHANGELOG_LINE = re.compile(r'^changelog:\s*"?(.+?)"?\s*$', re.MULTILINE)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class MissingPromptVariable(Exception):
    pass


@dataclass
class PromptArtifact:
    prompt_id: str
    version: str
    changelog: str
    text: str

    def render(self, **variables: str) -> str:
        placeholders = set(_PLACEHOLDER.findall(self.text))
        variables.setdefault("canary", CANARY)
        missing = placeholders - set(variables)
        if missing:
            raise MissingPromptVariable(
                f"{self.prompt_id}.{self.version} needs: {sorted(missing)}"
            )
        rendered = self.text
        for key, value in variables.items():
            rendered = rendered.replace("{{" + key + "}}", str(value))
        return rendered


def _parse(path: Path, prompt_id: str, version: str) -> PromptArtifact:
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    if not match:
        raise ValueError(f"{path} is missing --- front matter ---")
    front, body = match.groups()
    changelog_match = _CHANGELOG_LINE.search(front)
    if not changelog_match:
        raise ValueError(f"{path} is missing a changelog line in its front matter")
    return PromptArtifact(
        prompt_id=prompt_id, version=version, changelog=changelog_match.group(1).strip(), text=body.strip()
    )


def list_prompts() -> dict[str, list[str]]:
    prompts: dict[str, list[str]] = {}
    if not LIBRARY_ROOT.exists():
        return prompts
    for prompt_dir in sorted(p for p in LIBRARY_ROOT.iterdir() if p.is_dir()):
        versions = sorted(f.stem for f in prompt_dir.glob("v*.md"))
        if versions:
            prompts[prompt_dir.name] = versions
    return prompts


def load_prompt(key: str) -> PromptArtifact:
    prompt_id, _, version = key.partition(".")
    path = LIBRARY_ROOT / prompt_id / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"no such prompt: {key!r} (looked for {path})")
    return _parse(path, prompt_id, version)
