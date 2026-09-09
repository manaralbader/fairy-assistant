"""The one real adapter. This is the only file in the whole application that
is allowed to import ``openai`` — ``tests/test_architecture.py`` fails the
build if a second one shows up.

It works against any OpenAI-wire-compatible endpoint, which is what makes one
file enough for both required backends: point ``base_url`` at Google's Gemini
OpenAI-compatibility endpoint for the commercial route, or at Groq for the
open-weight route (both confirmed to speak this wire format). Provider swap is
two environment variables — see ``.env.example`` and ``fairy.llm.config`` —
never a code change.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import openai

from fairy.llm.interfaces import (
    FinishReason,
    LLMError,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    ToolCall,
    Usage,
)

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "stop": "stop",
    "length": "length",
    "tool_calls": "tool_calls",
    "content_filter": "refusal",
}


def _to_wire_messages(request: LLMRequest) -> list[dict]:
    wire = []
    for message in request.messages:
        entry: dict = {"role": message.role, "content": message.content}
        if message.tool_call_id:
            entry["tool_call_id"] = message.tool_call_id
        if message.name:
            entry["name"] = message.name
        if message.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in message.tool_calls
            ]
        wire.append(entry)
    return wire


def _from_wire_response(completion, *, route: str, latency_ms: float) -> LLMResponse:
    choice = completion.choices[0]
    message = choice.message
    tool_calls = [
        ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments)
        for call in (message.tool_calls or [])
    ]
    usage = completion.usage
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", 0) or 0
    return LLMResponse(
        text=message.content,
        tool_calls=tool_calls,
        finish_reason=_FINISH_REASON_MAP.get(choice.finish_reason, "stop"),
        model_id=completion.model,
        usage=Usage(
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cached_input_tokens=cached,
        ),
        latency_ms=latency_ms,
        route=route,
    )


def _translate_error(err: Exception) -> LLMError:
    status = getattr(getattr(err, "response", None), "status_code", None)
    retryable = status in (429, 500, 502, 503, 504) or isinstance(
        err, (openai.APIConnectionError, openai.APITimeoutError)
    )
    retry_after = None
    if status == 429:
        header = getattr(getattr(err, "response", None), "headers", {}).get("retry-after")
        retry_after = float(header) if header else 2.0
    return LLMError(str(err), status=status, retryable=retryable, retry_after=retry_after, raw=err)


class OpenAICompatClient:
    def __init__(self, *, api_key: str, base_url: str, model: str, route: str) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.route = route

    def complete(self, request: LLMRequest) -> LLMResponse:
        t0 = time.perf_counter()
        kwargs: dict = dict(
            model=self.model,
            messages=_to_wire_messages(request),
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        if request.tools:
            kwargs["tools"] = request.tools
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except openai.OpenAIError as err:
            raise _translate_error(err) from err
        return _from_wire_response(completion, route=self.route, latency_ms=(time.perf_counter() - t0) * 1000)

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        kwargs: dict = dict(
            model=self.model,
            messages=_to_wire_messages(request),
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        if request.tools:
            kwargs["tools"] = request.tools
        t0 = time.perf_counter()
        first_token_at: float | None = None
        try:
            for chunk in self._client.chat.completions.create(**kwargs):
                if not chunk.choices:
                    if chunk.usage:
                        yield StreamChunk(
                            final=True,
                            usage=Usage(
                                input_tokens=chunk.usage.prompt_tokens,
                                output_tokens=chunk.usage.completion_tokens,
                            ),
                            total_ms=(time.perf_counter() - t0) * 1000,
                            model_id=chunk.model,
                        )
                    continue
                delta = chunk.choices[0].delta.content or ""
                if delta and first_token_at is None:
                    first_token_at = time.perf_counter()
                yield StreamChunk(
                    delta=delta,
                    model_id=chunk.model,
                    ttft_ms=((first_token_at - t0) * 1000) if first_token_at else None,
                    finish_reason=_FINISH_REASON_MAP.get(chunk.choices[0].finish_reason or "", None),
                )
        except openai.OpenAIError as err:
            raise _translate_error(err) from err
