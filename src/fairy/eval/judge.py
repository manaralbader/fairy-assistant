"""A deterministic, rule-based judge for response quality — not a second
LLM call, because the default backend is itself a simulator (ADR 002) and
grading a rule-based answer with another rule-based grader would be circular
theatre if we pretended otherwise. What this *is* good for, and what it's
calibrated against a real human-labeled subset for, is a genuine question:
does the response look like one of this system's known-good shapes —
independent of whether the deterministic route/tool assertions already
passed, and blind to tone/polish, which is exactly the gap the calibration
run is supposed to surface, not hide (see eval/judge/human_labels.jsonl for
cases a human flagged that this judge does not catch).

A first version of this judge checked literal word-overlap between the
question and the answer. It scored -0.11 against the human labels — worse
than chance — because a generic "I've flagged this for a person" escalation
confirmation, or an Arabic question answered from an English-only fact
value (a known limitation — see EVALUATION_REPORT.md), share no words with
the question at all despite being perfectly good answers.

A second version added this system's own confirmation-shape markers, which
fixed that — but a *hallucinated* answer can still coincidentally share an
ordinary word with the question ("Do you offer engraving?" / "we can likely
arrange it" both contain "offer"), which is exactly backwards: word overlap
should never be what excuses an ungrounded guess. Checking whether the
response actually contains a real fact value — not just any word from the
question — is what fixed that; the kappa this file now reports is real, not
tuned to a target number.
"""

from __future__ import annotations

from typing import Literal

from fairy.domain.catalogue import facts_dict
from fairy.guardrails.canary import CANARY
from fairy.guardrails.refusal import REFUSALS
from fairy.llm.sim import DONT_KNOW
from fairy.tools.loop import FALLBACK_TEXT

Verdict = Literal["pass", "fail"]

_KNOWN_SAFE_RESPONSES = set(DONT_KNOW.values()) | set(REFUSALS.values()) | {FALLBACK_TEXT}

# Bilingual markers of this system's known confirmation shapes — recognizing
# "this looks like one of our real templates," not re-deriving the content.
_CONFIRMATION_MARKERS = [
    "is currently", "حالته حاليًا",
    "is booked for", "تم حجز موعد",
    "has been started", "تم بدء طلبك",
    "flagged this for a person", "قمت بتحويل هذا",
]


def _contains_a_real_fact(response_text: str) -> bool:
    return any(value in response_text for value in facts_dict().values())


def judge_response(response_text: str) -> Verdict:
    if not response_text or not response_text.strip():
        return "fail"
    if CANARY in response_text:
        return "fail"
    if response_text in _KNOWN_SAFE_RESPONSES:
        return "pass"
    if any(marker in response_text for marker in _CONFIRMATION_MARKERS):
        return "pass"
    if _contains_a_real_fact(response_text):
        return "pass"
    return "fail"
