"""The default backend — no API key, no network, no bill. See
docs/adr/002-the-default-backend.md for exactly what this keeps real (wire
shape, token accounting, prompt-cache hits, fault injection, grounding) and
what it simulates (answer quality, via two deterministic rule-based tiers).

Nothing here imports a provider SDK; it doesn't need to.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterator

from fairy.domain.catalogue import COLOR_PALETTE
from fairy.guardrails.normalize import normalize
from fairy.llm.interfaces import (
    LLMError,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    ToolCall,
    Usage,
)
from fairy.tools.confirmations import TOOL_CONFIRMATIONS

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

# Common function words in both languages, excluded from the FAQ
# keyword-overlap score below — without this, a question like "what is the
# turnaround time for a custom piece?" ties on "for"/"a" against an unrelated
# fact and picks the wrong one.
_STOPWORDS = {
    "what", "whats", "is", "are", "the", "a", "an", "for", "of", "to", "how",
    "much", "does", "do", "you", "your", "i", "can", "in", "on", "at", "it",
    "this", "that", "my", "me", "please", "and", "or", "will", "when",
    "ما", "هو", "هي", "في", "من", "الي", "هل", "شو", "و", "على", "عن", "قديش", "كم",
}


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", normalize(text)) if w not in _STOPWORDS}


# The facts are stored once, in English (fairy.domain.catalogue) — these are
# ONLY extra Arabic trigger words used to match an Arabic question to the
# right fact key. The catalogue's honest limitation (documented in
# EVALUATION_REPORT.md) is that the returned fact *value* is still English
# either way; this fixes matching, not translation.
FACT_KEY_ALIASES: dict[str, list[str]] = {
    "materials offered": ["مواد", "المواد", "خرز", "سلك"],
    "color palette": ["الوان", "ألوان", "لون"],
    "turnaround time": ["وقت التنفيذ", "مدة التنفيذ", "متى يجهز", "متى بيكون جاهز"],
    "defect and refund policy": ["ضمان", "خلل", "عيب", "استرداد", "استرجاع"],
    "pickup location": ["الاستوديو", "الموقع"],
    "pickup hours": ["ساعات العمل", "الدوام", "متى مفتوحين"],
    "price for a small piece": ["صغيرة", "صغير", "الصغيرة", "الصغير"],
    "price for a medium piece": ["متوسطة", "متوسط", "المتوسطة", "المتوسط"],
    "price for a statement piece": ["فخمة", "فخم", "الفخمة", "الفخم", "كبيرة", "الكبيرة"],
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


# A crude bilingual keyword extractor for create_custom_order — real code, not
# a live model, which is why answer *quality* is the one thing ADR 002 asks a
# reader not to trust from this file. It's what makes the validate → retry →
# repair loop's pass rate genuinely measurable per language rather than
# fabricated: the schema either validates what this actually extracted, or it
# doesn't.
AR_COLOR_MAP = {
    "لافندر": "lavender",
    "وردي": "blush pink",
    "زهري": "blush pink",
    "كريمي": "cream",
    "ذهبي": "gold",
    "فضي": "silver",
    "سماوي": "sky blue",
    "أرجواني": "lilac",
    "بنفسجي": "lilac",
}

BUDGET_KEYWORDS = {
    "small": ["bracelet", "earring", "earrings", "سوار", "أقراط"],
    "medium": ["necklace", "layered", "set", "قلادة", "طقم"],
    "statement": ["statement", "large", "multi-strand", "فخم", "كبير"],
}


def _extract_custom_order_args(text: str, *, miss: bool) -> dict:
    lowered = text.lower()
    colors = [c for c in COLOR_PALETTE if c in lowered]
    for arabic_word, mapped in AR_COLOR_MAP.items():
        if arabic_word in text and mapped not in colors:
            colors.append(mapped)
    if not colors:
        colors = ["gold"]
    colors = colors[:2]

    budget_tier = "small"
    for tier, keywords in BUDGET_KEYWORDS.items():
        if any(keyword in lowered or keyword in text for keyword in keywords):
            budget_tier = tier
            break

    args = {
        "color_preference": colors,
        "budget_tier": budget_tier,
        "inspiration_note": text.strip(),
    }
    if miss:
        # a real extraction failure mode: a required field goes missing
        # entirely, the same way a model sometimes forgets to fill one in.
        args.pop("budget_tier")
    return args


ORDER_ID_PATTERN = re.compile(r"FC-\d{4,}", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
TIME_SLOT_PATTERN = re.compile(r"\d{1,2}:\d{2}-\d{1,2}:\d{2}")
PHONE4_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")

REASON_KEYWORDS = {
    "defect_refund": [
        "broke", "broken", "defect", "snapped", "fell apart", "refund",
        "انكسر", "تكسر", "عيب", "استرداد",
    ],
    "over_specification_insisted": [
        "bead by bead", "stitch by stitch", "exactly", "precisely",
        "حبة حبة", "غرزة غرزة", "بالضبط", "بالتحديد",
    ],
}


def _extract_check_order_status_args(text: str, *, miss: bool) -> dict:
    args: dict = {}
    order_id_match = ORDER_ID_PATTERN.search(text)
    remainder = text
    if order_id_match:
        args["order_id"] = order_id_match.group(0).upper()
        remainder = text[: order_id_match.start()] + text[order_id_match.end() :]
    phone_match = PHONE4_PATTERN.search(remainder)
    if phone_match and not miss:
        args["phone_last4"] = phone_match.group(1)
    return args


def _extract_book_pickup_args(text: str, *, miss: bool) -> dict:
    args: dict = {}
    order_id_match = ORDER_ID_PATTERN.search(text)
    date_match = DATE_PATTERN.search(text)
    time_match = TIME_SLOT_PATTERN.search(text)
    if order_id_match:
        args["order_id"] = order_id_match.group(0).upper()
    if date_match:
        args["date"] = date_match.group(0)
    if time_match and not miss:
        args["time_slot"] = time_match.group(0)
    return args


def _extract_escalate_args(text: str, *, miss: bool) -> dict:
    lowered = text.lower()
    reason = "other"
    for candidate, keywords in REASON_KEYWORDS.items():
        if any(keyword in lowered or keyword in text for keyword in keywords):
            reason = candidate
            break
    args: dict = {"reason": reason, "details": text.strip()[:1000] or "no details given"}
    if miss:
        args.pop("reason")
    return args


class SimClient:
    def __init__(
        self,
        tier: str = "commercial",
        model_id: str | None = None,
        fault: str | None = None,
        real_sleep: bool = False,
        strict_grounding: bool = True,
    ) -> None:
        if tier not in TIER_PROFILES:
            raise ValueError(f"unknown sim tier: {tier!r} — choose one of {sorted(TIER_PROFILES)}")
        self.tier = tier
        self.model_id = model_id or f"fairy-sim-{tier}"
        self.route = f"sim:{tier}"
        self.fault = fault  # None | "rate_limit" | "outage" — set to drive the reliability drill
        self._real_sleep = real_sleep  # False in tests/CI so the suite stays fast
        # False stands in for what a real model given prompts/library/answer_faq/v2.md
        # would do — that version's changelog quietly drops the don't-know
        # instruction. Our backend doesn't read prose, so the matching
        # behavior is toggled here instead of actually being driven by the
        # prompt text; see docs/adr/002 and DECISIONS.md for why that's
        # the honest way to seed this regression against a rule-based sim.
        self.strict_grounding = strict_grounding
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
            prior = self._prior_tool_message(request.messages)
            if prior is not None and self._parses_as_success(prior.content):
                text_out = self._summarize_tool_result(prior.name, prior.content, request.messages)
                tool_calls, finish = [], "stop"
            else:
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

        question_words = _content_words(last_user)
        best_key, best_score = None, 0
        for key in facts:
            key_words = _content_words(key) | _content_words(" ".join(FACT_KEY_ALIASES.get(key, [])))
            overlap = len(question_words & key_words)
            if overlap > best_score:
                best_key, best_score = key, overlap

        if best_key is None or best_score == 0:
            if not self.strict_grounding:
                return self._degraded_guess(last_user, language)
            return DONT_KNOW[language]
        if roll < profile["miss_rate"]:
            # the simulated failure mode: the fact WAS in the directory and
            # got missed anyway — this is what a groundedness eval slice
            # exists to catch, per tier.
            return DONT_KNOW[language]
        return f"{best_key}: {facts[best_key]}"

    def _degraded_guess(self, question: str, language: str) -> str:
        """The seeded regression: a friendlier tone that stops refusing and
        guesses instead — plausible-sounding, ungrounded, and wrong. Never
        invents a money figure (that's the groundedness guard's job to
        catch); this is specifically the failure shape a *golden-set* slice
        exists to catch, not the guard."""
        if language == "ar":
            return "على الأغلب هذا شبيه بما تقدمه استوديوهات مماثلة، يمكننا الترتيب لذلك."
        return "That's probably similar to what comparable studios offer — we can likely arrange it."

    def _prior_tool_message(self, messages):
        for message in reversed(messages):
            if message.role == "tool":
                return message
        return None

    def _parses_as_success(self, content: str) -> bool:
        """A tool result is JSON (fairy.tools.loop encodes success this way);
        a validation/tool error is a prose string. That distinction — not
        randomness — is what tells the simulator whether to try the tool
        again or stop and summarize."""
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return False
        return isinstance(payload, dict)

    def _summarize_tool_result(self, tool_name: str, content: str, messages) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        language = "ar" if re.search(r"[؀-ۿ]", last_user) else "en"
        payload = json.loads(content)
        template = TOOL_CONFIRMATIONS.get(tool_name, {}).get(language)
        if template is None:
            return DONT_KNOW[language]
        return template(payload)

    def _answer_with_tool(self, request: LLMRequest, roll: float, profile: dict):
        tool = request.tools[0]
        name = tool.get("function", {}).get("name") or tool.get("name", "unknown_tool")
        if roll < profile["schema_fumble_rate"]:
            return "", [ToolCall(id="sim_call_1", name=name, arguments="{not valid json")], "tool_calls"
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        miss = roll < profile["miss_rate"]
        if name == "create_custom_order":
            args = _extract_custom_order_args(last_user, miss=miss)
        elif name == "check_order_status":
            args = _extract_check_order_status_args(last_user, miss=miss)
        elif name == "book_pickup_appointment":
            args = _extract_book_pickup_args(last_user, miss=miss)
        elif name == "escalate_to_human":
            args = _extract_escalate_args(last_user, miss=miss)
        else:
            args = {}
        return "", [ToolCall(id="sim_call_1", name=name, arguments=json.dumps(args, ensure_ascii=False))], "tool_calls"

    def _simulate_latency(self, out_tokens: int, profile: dict) -> None:
        if not self._real_sleep:
            return
        time.sleep((out_tokens * profile["ms_per_out_tok"]) / 1000)
