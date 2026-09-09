"""Architecture rules, enforced by a test rather than by hoping.

Three claims this codebase makes, each only true for as long as something
checks it:

1. application code never imports a provider SDK directly;
2. prompt text lives in versioned files under ``fairy/prompts/library``, never
   inline in Python;
3. no model call is unbounded — ``max_tokens`` is always passed explicitly.

These run locally with pytest, and the same checks are re-run as plain
``assert`` cells inside the capstone notebook — a reader going through the
notebook top to bottom sees the same claim proven, not just asserted here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "fairy"
ALLOWED_SDK_IMPORTERS = {"openai_compat.py"}


def python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_provider_sdk_outside_the_adapter():
    offenders: list[str] = []
    for path in python_files(SRC):
        if path.name in ALLOWED_SDK_IMPORTERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if name.split(".")[0] in {"openai", "anthropic"}:
                    offenders.append(f"{path.relative_to(SRC)}:{node.lineno} imports {name}")
    assert offenders == [], (
        "provider SDKs belong behind the boundary. Every one of these turns a "
        "config change into a rewrite:\n  " + "\n  ".join(offenders)
    )


def test_no_inline_prompt_text_in_code():
    """A crude but effective grep: system-prompt-shaped string literals outside
    the prompt registry are the thing this test exists to catch."""
    pattern = re.compile(r'"(?:[^"\n]*\b(?:You are|أنت مساعد|أنت مساعدة)\b[^"\n]*)"')
    offenders = []
    for path in python_files(SRC):
        if path.parts[-2:] == ("prompts", "registry.py"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line):
                offenders.append(f"{path.relative_to(SRC)}:{number}: {line.strip()[:70]}")
    assert offenders == [], (
        "prompt text lives in src/fairy/prompts/library as a versioned file:\n  "
        + "\n  ".join(offenders)
    )


def test_every_llm_request_call_site_bounds_max_tokens():
    """Belt-and-braces on top of the pydantic field being required: a static
    check that fails before the code even runs."""
    offenders = []
    for path in python_files(SRC):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "LLMRequest":
                continue
            keywords = {kw.arg for kw in node.keywords}
            if "max_tokens" not in keywords:
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert offenders == [], (
        "a request without max_tokens is a demo default that becomes a "
        "production incident:\n  " + "\n  ".join(offenders)
    )
