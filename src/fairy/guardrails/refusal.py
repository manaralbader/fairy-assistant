"""Stage 5: decision and refusal composition. Every refusal is a fixed,
bilingual, pre-written sentence — never the attacker's own text reflected
back, and never assembled from anything in the request. That's deliberate:
an echoed payload is itself a leak, and a dynamically composed refusal is one
more thing an attacker could try to influence.
"""

from __future__ import annotations

from typing import Literal

Reason = Literal["injection_detected", "canary_leak", "unsupported_claim"]
Language = Literal["en", "ar"]

REFUSALS: dict[tuple[Reason, Language], str] = {
    ("injection_detected", "en"): (
        "I can't do that. I'm happy to help with anything about Fairycore's "
        "pieces, an order, or a pickup instead."
    ),
    ("injection_detected", "ar"): (
        "لا يمكنني تنفيذ ذلك. يسعدني مساعدتك بخصوص قطع فيري كور أو طلبك أو موعد الاستلام."
    ),
    ("canary_leak", "en"): "I can't share that. How else can I help with your Fairycore order?",
    ("canary_leak", "ar"): "لا يمكنني مشاركة ذلك. كيف يمكنني مساعدتك بخصوص طلبك من فيري كور؟",
    ("unsupported_claim", "en"): (
        "I don't have confirmed information on that — let me connect you with a person who does."
    ),
    ("unsupported_claim", "ar"): (
        "لا تتوفر لدي معلومات مؤكدة حول ذلك، سأقوم بتحويلك لأحد أفراد الفريق."
    ),
}


def compose_refusal(reason: Reason, language: Language) -> str:
    try:
        return REFUSALS[(reason, language)]
    except KeyError as err:
        raise ValueError(f"no refusal text for reason={reason!r} language={language!r}") from err
