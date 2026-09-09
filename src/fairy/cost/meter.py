"""Wraps any LLMClient and records every call — 100% coverage is a property
of *where* this wrapper sits (the router's only call sites), not a claim
that needs re-checking per call site."""

from __future__ import annotations

from dataclasses import dataclass, field

from fairy.llm.interfaces import LLMClient, LLMRequest, LLMResponse

PRICE_PER_1K_TOKENS = {
    "commercial": {"input": 0.00015, "cached_input": 0.000075, "output": 0.0006},
    "open_weight": {"input": 0.00003, "cached_input": 0.000015, "output": 0.00012},
}


@dataclass
class MeterRecord:
    route: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    latency_ms: float
    cost_usd: float


class MeteredClient:
    def __init__(self, inner: LLMClient, tier: str = "commercial") -> None:
        self.inner = inner
        self.tier = tier
        self.records: list[MeterRecord] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self.inner.complete(request)
        self.records.append(self._record(response))
        return response

    def stream(self, request: LLMRequest):
        return self.inner.stream(request)

    def _record(self, response: LLMResponse) -> MeterRecord:
        price = PRICE_PER_1K_TOKENS.get(self.tier, PRICE_PER_1K_TOKENS["commercial"])
        billable_input = max(0, response.usage.input_tokens - response.usage.cached_input_tokens)
        cost = (
            (billable_input / 1000) * price["input"]
            + (response.usage.cached_input_tokens / 1000) * price["cached_input"]
            + (response.usage.output_tokens / 1000) * price["output"]
        )
        return MeterRecord(
            route=response.route,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_input_tokens=response.usage.cached_input_tokens,
            latency_ms=response.latency_ms,
            cost_usd=cost,
        )

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def cache_hit_rate(self) -> float:
        total_in = sum(r.input_tokens for r in self.records)
        cached = sum(r.cached_input_tokens for r in self.records)
        return cached / total_in if total_in else 0.0

    @property
    def call_count(self) -> int:
        return len(self.records)
