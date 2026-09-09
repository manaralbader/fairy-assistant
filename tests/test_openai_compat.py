"""OpenAICompatClient tests, all against a mocked HTTP layer — no network, no
key required. What's under test is the request/response mapping, not any
real provider's behaviour."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest

from fairy.llm.interfaces import LLMError, LLMRequest, Message
from fairy.llm.openai_compat import OpenAICompatClient


def req(**overrides) -> LLMRequest:
    defaults = dict(messages=[Message(role="user", content="hi")], max_tokens=200)
    defaults.update(overrides)
    return LLMRequest(**defaults)


def fake_completion(text="hello", finish_reason="stop", tool_calls=None):
    message = SimpleNamespace(content=text, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=50, completion_tokens=10, prompt_tokens_details=None)
    return SimpleNamespace(choices=[choice], usage=usage, model="stand-in-model")


def make_client() -> OpenAICompatClient:
    client = OpenAICompatClient(api_key="x", base_url="https://example.invalid/v1", model="m", route="commercial")
    client._client = MagicMock()
    return client


def test_complete_maps_a_plain_text_response():
    client = make_client()
    client._client.chat.completions.create.return_value = fake_completion(text="hi there")
    response = client.complete(req())
    assert response.text == "hi there"
    assert response.finish_reason == "stop"
    assert response.usage.input_tokens == 50
    assert response.usage.output_tokens == 10
    assert response.route == "commercial"


def test_complete_maps_tool_calls():
    tool_call = SimpleNamespace(id="c1", function=SimpleNamespace(name="check_order_status", arguments="{}"))
    client = make_client()
    client._client.chat.completions.create.return_value = fake_completion(
        text=None, finish_reason="tool_calls", tool_calls=[tool_call]
    )
    response = client.complete(req())
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].name == "check_order_status"


def test_max_tokens_is_always_forwarded():
    client = make_client()
    client._client.chat.completions.create.return_value = fake_completion()
    client.complete(req(max_tokens=321))
    _, kwargs = client._client.chat.completions.create.call_args
    assert kwargs["max_tokens"] == 321


def test_provider_error_is_translated_to_llm_error_with_retryable_flag():
    client = make_client()
    response_mock = SimpleNamespace(status_code=429, headers={"retry-after": "3"}, request=None)
    client._client.chat.completions.create.side_effect = openai.RateLimitError(
        "rate limited", response=response_mock, body=None
    )
    with pytest.raises(LLMError) as excinfo:
        client.complete(req())
    assert excinfo.value.status == 429
    assert excinfo.value.retryable is True
    assert excinfo.value.retry_after == 3.0
