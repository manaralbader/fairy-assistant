"""The model boundary. Every other module in this application imports THIS —
never a provider SDK directly.

Three implementations exist behind it: :class:`~fairy.llm.openai_compat.OpenAICompatClient`
(any real, OpenAI-wire-compatible provider — commercial or open-weight, chosen by
config), :class:`~fairy.llm.sim.SimClient` (the in-process, no-key default —
see docs/adr/002), and :class:`~fairy.llm.fake.FakeClient` (scripted responses,
used only by tests).

``tests/test_architecture.py`` enforces the claim this file makes: no file
outside ``fairy/llm/`` may import ``openai`` or ``anthropic``, and no
``LLMRequest`` may be built without ``max_tokens``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

FinishReason = Literal["stop", "length", "tool_calls", "refusal", "error"]


class ToolCall(BaseModel):
    """A tool the model wants the application to run. The model never runs it itself."""

    id: str
    name: str
    arguments: str  # raw JSON string; parsed and validated by the tool layer


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMRequest(BaseModel):
    messages: list[Message]
    model_alias: str = "fairy-default"  # resolved to a concrete route via config, never hardcoded
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(..., gt=0)  # required — no unbounded call is allowed to exist
    tools: list[dict] | None = None  # provider-neutral JSON schema
    response_format: dict | None = None
    cache_prefix_messages: int = 0  # how many leading messages form the stable, cacheable prefix


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


class LLMResponse(BaseModel):
    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: FinishReason = "stop"
    model_id: str = ""  # the concrete model that actually answered
    usage: Usage = Field(default_factory=Usage)
    latency_ms: float = 0.0
    route: str = ""  # which configured route served the request


class StreamChunk(BaseModel):
    delta: str = ""
    final: bool = False
    usage: Usage | None = None
    ttft_ms: float | None = None
    total_ms: float | None = None
    model_id: str = ""
    finish_reason: FinishReason | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Everything application code is allowed to know about a model provider."""

    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]: ...


class LLMError(RuntimeError):
    """A normalised provider failure. ``retryable`` drives the retry/fallback policy."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        raw: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.raw = raw

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        return f"LLMError(status={self.status}, retryable={self.retryable}, msg={self!s})"
