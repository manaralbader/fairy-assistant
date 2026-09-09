"""Unit tests for the model boundary itself: the request contract, the fake
client used everywhere else in the test suite, and the retry/fallback wrapper
that the Module 1 reliability drill exercises."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fairy.llm.fake import FakeClient
from fairy.llm.interfaces import LLMError, LLMRequest, Message
from fairy.llm.resilient import ResilientClient


def make_request(**overrides) -> LLMRequest:
    defaults = dict(
        messages=[Message(role="user", content="hi")],
        max_tokens=200,
    )
    defaults.update(overrides)
    return LLMRequest(**defaults)


def test_llm_request_requires_max_tokens():
    with pytest.raises(ValidationError):
        LLMRequest(messages=[Message(role="user", content="hi")])


def test_fake_client_replays_scripted_text():
    client = FakeClient().script_text("hello there")
    response = client.complete(make_request())
    assert response.text == "hello there"
    assert client.call_count == 1


def test_fake_client_raises_scripted_error():
    client = FakeClient().script_rate_limit(times=1)
    with pytest.raises(LLMError):
        client.complete(make_request())


def test_resilient_client_retries_then_succeeds_on_primary():
    primary = FakeClient(route="primary").script_rate_limit(times=1).script_text("recovered")
    wrapped = ResilientClient(primary, sleep_fn=lambda _s: None)
    response = wrapped.complete(make_request())
    assert response.text == "recovered"
    assert wrapped.log[0]["outcome"] == "error"
    assert wrapped.log[1]["outcome"] == "ok"


def test_resilient_client_falls_back_after_exhausting_retries():
    primary = FakeClient(route="primary").script_rate_limit(times=5)
    fallback = FakeClient(route="fallback").script_text("from the fallback")
    wrapped = ResilientClient(primary, fallback, max_retries=2, sleep_fn=lambda _s: None)
    response = wrapped.complete(make_request())
    assert response.text == "from the fallback"
    assert response.route == "fallback"
    outcomes = [event["backend"] for event in wrapped.log]
    assert outcomes.count("primary") == 3  # 1 initial + 2 retries, all failed
    assert outcomes[-1] == "fallback"


def test_resilient_client_raises_without_fallback_when_exhausted():
    primary = FakeClient(route="primary").script_outage(times=5)
    wrapped = ResilientClient(primary, max_retries=1, sleep_fn=lambda _s: None)
    with pytest.raises(LLMError):
        wrapped.complete(make_request())
