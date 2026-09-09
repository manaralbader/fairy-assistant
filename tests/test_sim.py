"""Tests for the default (no-key) backend: grounding, cache-hit accounting,
fault injection, and reproducibility of the per-tier failure simulation."""

from __future__ import annotations

from fairy.llm.interfaces import LLMError, LLMRequest, Message
from fairy.llm.sim import SimClient


def req(messages, **overrides) -> LLMRequest:
    return LLMRequest(messages=messages, max_tokens=200, **overrides)


def test_answers_only_from_facts_present_in_the_system_message():
    client = SimClient(tier="commercial")
    system = "You are Fairycore's assistant.\nFACT: turnaround time = 7-10 business days\n"
    response = client.complete(
        req([Message(role="system", content=system), Message(role="user", content="what is the turnaround time?")])
    )
    assert "7-10 business days" in response.text


def test_refuses_a_question_with_no_matching_fact():
    client = SimClient(tier="commercial")
    system = "FACT: turnaround time = 7-10 business days\n"
    response = client.complete(
        req([Message(role="system", content=system), Message(role="user", content="do you ship internationally?")])
    )
    assert "7-10" not in response.text
    assert response.text  # some refusal text came back


def test_refuses_in_arabic_for_an_arabic_question():
    client = SimClient(tier="commercial")
    response = client.complete(
        req([Message(role="system", content="FACT: x = y"), Message(role="user", content="هل تشحنون دوليا؟")])
    )
    assert any("؀" <= ch <= "ۿ" for ch in response.text)


def test_prompt_cache_hits_only_on_a_repeated_stable_prefix():
    client = SimClient(tier="commercial")
    prefix = Message(role="system", content="FACT: turnaround time = 7-10 business days")
    request = req([prefix, Message(role="user", content="turnaround time?")], cache_prefix_messages=1)

    first = client.complete(request)
    second = client.complete(request)

    assert first.usage.cached_input_tokens == 0
    assert second.usage.cached_input_tokens > 0


def test_fault_injection_raises_retryable_rate_limit():
    client = SimClient(tier="commercial", fault="rate_limit")
    try:
        client.complete(req([Message(role="user", content="hi")]))
        assert False, "expected LLMError"
    except LLMError as err:
        assert err.status == 429
        assert err.retryable is True


def test_fault_injection_raises_retryable_outage():
    client = SimClient(tier="open_weight", fault="outage")
    try:
        client.complete(req([Message(role="user", content="hi")]))
        assert False, "expected LLMError"
    except LLMError as err:
        assert err.status == 503
        assert err.retryable is True


def test_the_same_input_produces_the_same_tool_call_outcome_every_time():
    """The per-tier degradation is a hash of the request, not randomness — a
    failing case is reproducible, which is the whole point of simulating."""
    tool = {"function": {"name": "check_order_status", "parameters": {}}}
    outcomes = set()
    for _ in range(3):
        client = SimClient(tier="open_weight")
        response = client.complete(
            req([Message(role="user", content="where is order 42")], tools=[tool])
        )
        outcomes.add(response.tool_calls[0].arguments)
    assert len(outcomes) == 1, "same input should reproduce the same simulated outcome"


def test_open_weight_tier_fumbles_tool_json_more_often_than_commercial():
    tool = {"function": {"name": "check_order_status", "parameters": {}}}
    prompts = [f"where is order {i}" for i in range(200)]

    def fumble_rate(tier: str) -> float:
        fumbles = 0
        for prompt in prompts:
            client = SimClient(tier=tier)
            response = client.complete(req([Message(role="user", content=prompt)], tools=[tool]))
            if "not valid json" in response.tool_calls[0].arguments:
                fumbles += 1
        return fumbles / len(prompts)

    assert fumble_rate("open_weight") > fumble_rate("commercial")
