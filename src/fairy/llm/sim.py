"""The default backend — no API key, no network, no bill. See
docs/adr/002-the-default-backend.md for exactly what this keeps real (wire
shape, token accounting, prompt-cache hits, fault injection, grounding) and
what it simulates (answer quality, via two deterministic rule-based tiers).

Nothing here imports a provider SDK; it doesn't need to.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterator

from fairy.llm.interfaces import (
    LLMClient,
    LLMError,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    ToolCall,
    Usage,
)

# Deliberately crude: ~4 characters per token is a reasonable English average
# and an underestimate for Arabic. Good enough for a simulator whose job is to
# produce a real, countable number — never quoted as a real tokenizer's output.
def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


FACT_LINE = re.compile(r"^\s*FACT:\s*([^=]+?)\s*=\s*(.+?)\s*$", re.MULTILINE)

DONT_KNOW = {
    "en": "I don't have that information — let me connect you with a person who does.",
    "ar": "لا تتوفر لدي هذه المعلومة، سأقوم بتحويلك لأحد أفراد الفريق.",
}

TIER_PROFILES = {
    # schema_fumble_rate: how often a tool call comes back with malformed
    # JSON arguments — a real failure mode, simulated deterministically.
    # miss_rate: how often a fact that IS in the directory gets missed anyway.
    "commercial": {"schema_fumble_rate": 0.02, "miss_rate": 0.03, "ms_per_out_tok": 18},
    "open_weight": {"schema_fumble_rate": 0.10, "miss_rate": 0.12, "ms_per_out_tok": 9},
}


def _deterministic_unit_interval(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) % 10_000) / 10_000


class SimClient:
    def __init__(
        self,
        tier: str = "commercial",
        model_id: str | None = None,
        fault: str | None = None,
        real_sleep: bool = False,
    ) -> None:
        if tier not in TIER_PROFILES:
            raise ValueError(f"unknown sim tier: {tier!r} — choose one of {sorted(TIER_PROFILES)}")
        self.tier = tier
        self.model_id = model_id or f"fairy-sim-{tier}"
        self.route = f"sim:{tier}"
        self.fault = fault  # None | "rate_limit" | "outage" — set to drive the reliability drill
        self._real_sleep = real_sleep  # False in tests/CI so the suite stays fast
        self._prefix_tokens_seen: dict[str, int] = {}
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.fault == "rate_limit":
            raise LLMError("simulated 429 rate limit", status=429, retryable=True, retry_after=1.0)
        if self.fault == "outage":
            raise LLMError("simulated 503 service unavailable", status=503, retryable=True)

        t0 = time.perf_counter()
        profile = TIER_PROFILES[self.tier]
        prompt_text = "\n".join(m.content for m in request.messages)
        in_tokens = _approx_tokens(prompt_text)
        cached = self._score_cache(request)

        roll = _deterministic_unit_interval(self.tier, prompt_text)

        if request.tools:
            text_out, tool_calls, finish = self._answer_with_tool(request, roll, profile)
        else:
            text_out = self._answer_faq(request, roll, profile)
            tool_calls, finish = [], "stop"

        out_tokens = _approx_tokens(text_out) if text_out else 20
        self._simulate_latency(out_tokens, profile)

        return LLMResponse(
            text=text_out or None,
            tool_calls=tool_calls,
            finish_reason=finish,
            model_id=self.model_id,
            usage=Usage(input_tokens=in_tokens, output_tokens=out_tokens, cached_input_tokens=cached),
            latency_ms=(time.perf_counter() - t0) * 1000,
            route=self.route,
        )

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        response = self.complete(request)
        for word in (response.text or "").split(" "):
            if word:
                yield StreamChunk(delta=word + " ", model_id=response.model_id)
        yield StreamChunk(
            final=True,
            usage=response.usage,
            model_id=response.model_id,
            finish_reason=response.finish_reason,
        )

    # --- internals ---------------------------------------------------------

    def _score_cache(self, request: LLMRequest) -> int:
        """A real cache-hit mechanism: hash the stable prefix, remember its
        token count, and only report a hit the second time that EXACT prefix
        (byte for byte) shows up again — same discipline a real provider's
        prompt cache uses."""
        if not request.cache_prefix_messages:
            return 0
        prefix_text = "\n".join(m.content for m in request.messages[: request.cache_prefix_messages])
        key = hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()
        previously_seen = self._prefix_tokens_seen.get(key, 0)
        self._prefix_tokens_seen[key] = _approx_tokens(prefix_text)
        return previously_seen

    def _answer_faq(self, request: LLMRequest, roll: float, profile: dict) -> str:
        system_text = "\n".join(m.content for m in request.messages if m.role == "system")
        facts = dict(FACT_LINE.findall(system_text))
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        language = "ar" if re.search(r"[؀-ۿ]", last_user) else "en"

        if not facts:
            return DONT_KNOW[language]

        question_words = set(re.findall(r"\w+", last_user.lower()))
        best_key, best_score = None, 0
        for key in facts:
            key_words = set(re.findall(r"\w+", key.lower()))
            overlap = len(question_words & key_words)
            if overlap > best_score:
                best_key, best_score = key, overlap

        if best_key is None or best_score == 0:
            return DONT_KNOW[language]
        if roll < profile["miss_rate"]:
            # the simulated failure mode: the fact WAS in the directory and
            # got missed anyway — this is what a groundedness eval slice
            # exists to catch, per tier.
            return DONT_KNOW[language]
        return f"{best_key}: {facts[best_key]}"

    def _answer_with_tool(self, request: LLMRequest, roll: float, profile: dict):
        tool = request.tools[0]
        name = tool.get("function", {}).get("name") or tool.get("name", "unknown_tool")
        if roll < profile["schema_fumble_rate"]:
            return "", [ToolCall(id="sim_call_1", name=name, arguments="{not valid json")], "tool_calls"
        return "", [ToolCall(id="sim_call_1", name=name, arguments="{}")], "tool_calls"

    def _simulate_latency(self, out_tokens: int, profile: dict) -> None:
        if not self._real_sleep:
            return
        time.sleep((out_tokens * profile["ms_per_out_tok"]) / 1000)
