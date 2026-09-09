from __future__ import annotations

import pytest

from fairy.guardrails.canary import CANARY
from fairy.prompts.registry import MissingPromptVariable, list_prompts, load_prompt


def test_answer_faq_v1_is_registered():
    prompts = list_prompts()
    assert "answer_faq" in prompts
    assert "v1" in prompts["answer_faq"]


def test_every_prompt_has_a_changelog():
    for prompt_id, versions in list_prompts().items():
        for version in versions:
            artifact = load_prompt(f"{prompt_id}.{version}")
            assert artifact.changelog


def test_rendering_without_a_required_variable_fails_loudly():
    prompt = load_prompt("answer_faq.v1")
    with pytest.raises(MissingPromptVariable):
        prompt.render()


def test_the_canary_is_planted_in_every_rendered_system_prompt():
    rendered = load_prompt("answer_faq.v1").render(service_directory="FACT: x = y")
    assert CANARY in rendered


def test_rendering_substitutes_the_service_directory():
    rendered = load_prompt("answer_faq.v1").render(service_directory="FACT: turnaround = 7-10 days")
    assert "FACT: turnaround = 7-10 days" in rendered
