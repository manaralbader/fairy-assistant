"""Router-first: exactly one of three shapes runs per customer turn — a
single-call FAQ answer, a bounded tool workflow, or a direct escalation to a
human. The guard wall wraps both ends: an attack never reaches a model call
(stages 1-2 run first), and every response is checked for a leaked canary or
an invented figure before a customer ever sees it (stages 3-4, always last).

Route selection here is a fixed, bilingual keyword lookup — deliberately
simple and fully deterministic, which is what makes the golden set's routing
expectations testable with a plain assert instead of a judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import json

from fairy.domain.catalogue import facts_dict, to_fact_lines
from fairy.guardrails.normalize import detect_language
from fairy.guardrails.pipeline import check_input, check_output
from fairy.llm.interfaces import LLMClient, LLMRequest, Message
from fairy.prompts.registry import load_prompt
from fairy.tools.confirmations import TOOL_CONFIRMATIONS
from fairy.tools.loop import run_tool_loop
from fairy.tools.registry import TOOLS
from fairy.tools.session import Session
from fairy.tools.store import OrderStore

_ESCALATION_KEYWORDS = [
    "broke", "broken", "defect", "snapped", "fell apart", "refund",
    "speak to someone", "speak to a person", "human",
    "انكسر", "تكسر", "عيب", "استرداد", "موظف", "شخص حقيقي",
]
_ORDER_STATUS_KEYWORDS = [
    "status", "where is my order", "track my order", "ready yet", "when will my order",
    "حالة الطلب", "وين طلبي", "متابعة طلبي", "طلبي جاهز",
]
_APPOINTMENT_KEYWORDS = [
    "pickup", "pick up", "appointment", "book a", "collect my",
    "استلام", "موعد", "احجز", "أحجز",
]
_NEW_ORDER_KEYWORDS = [
    "custom order", "commission", "new order", "want a bracelet", "want a necklace",
    "want a set", "want earrings",
    "أطلب", "اطلب", "سوار", "قلادة", "أقراط", "اقراط", "طقم", "أبغى", "ابغى",
]


def _any_keyword(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


@dataclass
class RouterResult:
    route: str  # "blocked" | "faq" | "service_workflow" | "escalation"
    final_text: str
    guard_stages: list = field(default_factory=list)
    tool_log: list = field(default_factory=list)


def _run_single_tool_workflow(
    tool_name: str,
    user_text: str,
    *,
    client: LLMClient,
    session: Session,
    store: OrderStore,
) -> tuple[str, list]:
    result = run_tool_loop(
        client,
        [Message(role="user", content=user_text)],
        session=session,
        store=store,
        tools=[TOOLS[tool_name].json_schema],
        # room for: a fumble on attempt 1, a successful retry, and a turn to
        # compose the confirmation the customer actually sees.
        max_iterations=3,
    )
    final_text = result.final_text or ""

    # A terminal tool (escalate_to_human) ends the loop the instant it
    # succeeds — no backend, real or simulated, ever gets a turn to compose
    # a summary for it, so the router composes one here instead of showing
    # the tool's raw JSON result directly.
    if result.log and result.log[-1].get("outcome") == "ok":
        try:
            payload = json.loads(final_text)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            template = TOOL_CONFIRMATIONS.get(tool_name, {}).get(detect_language(user_text))
            if template is not None:
                final_text = template(payload)

    return final_text, result.log


def handle_turn(
    user_text: str,
    *,
    client: LLMClient,
    session: Session,
    store: OrderStore,
    max_tokens: int = 300,
    response_cache=None,
) -> RouterResult:
    blocked = check_input(user_text)
    if blocked is not None:
        return RouterResult(route="blocked", final_text=blocked.output_text, guard_stages=blocked.stages)

    language = detect_language(user_text)

    is_tool_intent = (
        _any_keyword(user_text, _ESCALATION_KEYWORDS)
        or _any_keyword(user_text, _ORDER_STATUS_KEYWORDS)
        or _any_keyword(user_text, _APPOINTMENT_KEYWORDS)
        or _any_keyword(user_text, _NEW_ORDER_KEYWORDS)
    )
    if not is_tool_intent and response_cache is not None:
        cached = response_cache.get(user_text, language)
        if cached is not None:
            return RouterResult(route="faq", final_text=cached, guard_stages=[], tool_log=[])

    if _any_keyword(user_text, _ESCALATION_KEYWORDS):
        raw_text, tool_log = _run_single_tool_workflow(
            "escalate_to_human", user_text, client=client, session=session, store=store
        )
        route = "escalation"
    elif _any_keyword(user_text, _ORDER_STATUS_KEYWORDS):
        raw_text, tool_log = _run_single_tool_workflow(
            "check_order_status", user_text, client=client, session=session, store=store
        )
        route = "service_workflow"
    elif _any_keyword(user_text, _APPOINTMENT_KEYWORDS):
        raw_text, tool_log = _run_single_tool_workflow(
            "book_pickup_appointment", user_text, client=client, session=session, store=store
        )
        route = "service_workflow"
    elif _any_keyword(user_text, _NEW_ORDER_KEYWORDS):
        raw_text, tool_log = _run_single_tool_workflow(
            "create_custom_order", user_text, client=client, session=session, store=store
        )
        route = "service_workflow"
    else:
        system_prompt = load_prompt("answer_faq.v1").render(service_directory=to_fact_lines())
        response = client.complete(
            LLMRequest(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_text),
                ],
                max_tokens=max_tokens,
                cache_prefix_messages=1,  # the system prompt is the stable, cacheable prefix
            )
        )
        raw_text, tool_log, route = response.text or "", [], "faq"

    guarded = check_output(raw_text, facts=facts_dict(), language=language)
    if route == "faq" and response_cache is not None and guarded.verdict == "allow":
        response_cache.set(user_text, language, guarded.output_text)
    return RouterResult(route=route, final_text=guarded.output_text, guard_stages=guarded.stages, tool_log=tool_log)
