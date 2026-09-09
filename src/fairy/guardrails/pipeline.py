"""The five stages, wired together — but written so each one can also be
called on its own, which is what "demonstrated alone in its own cell" means
in practice: ``normalize()``, ``detect_injection()``, ``check_canary_leak()``,
``check_groundedness()`` and ``compose_refusal()`` all work standalone; this
module is just the sequencing.

    1. normalize      — fold the input to one canonical form
    2. detect_injection — look for an attack shape in the normalized input
    3. check_canary_leak — after the model answers, did it echo the canary?
    4. check_groundedness — does the answer state a figure not in the facts?
    5. decide          — compose a bilingual refusal, or let the answer through

An input that fails stage 2 never reaches a model call at all — stages 3/4
only make sense once there's a response to check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fairy.guardrails.canary import check_canary_leak
from fairy.guardrails.groundedness import check_groundedness
from fairy.guardrails.normalize import detect_language, normalize
from fairy.guardrails.patterns import detect_injection
from fairy.guardrails.refusal import compose_refusal


@dataclass
class StageResult:
    stage: str
    passed: bool
    detail: str = ""


@dataclass
class PipelineResult:
    verdict: str  # "allow" | "block"
    output_text: str
    stages: list[StageResult] = field(default_factory=list)


def check_input(user_text: str) -> PipelineResult | None:
    """Stages 1-2. Returns a blocking ``PipelineResult`` if the input itself
    is an attack, or ``None`` if it's safe to send to a model."""
    normalized = normalize(user_text)
    stages = [StageResult("normalize", True, detail=normalized)]

    matches = detect_injection(normalized)
    if matches:
        stages.append(StageResult("injection_detection", False, detail=",".join(matches)))
        refusal = compose_refusal("injection_detected", detect_language(user_text))
        return PipelineResult(verdict="block", output_text=refusal, stages=stages)

    stages.append(StageResult("injection_detection", True))
    return None


def check_output(response_text: str, *, facts: dict[str, str], language: str) -> PipelineResult:
    """Stages 3-4, plus the decision (stage 5)."""
    stages: list[StageResult] = []

    leaked = check_canary_leak(response_text)
    stages.append(StageResult("canary_check", not leaked, detail="leaked" if leaked else ""))
    if leaked:
        return PipelineResult(
            verdict="block", output_text=compose_refusal("canary_leak", language), stages=stages
        )

    unsupported = check_groundedness(response_text, facts)
    stages.append(StageResult("groundedness_check", not unsupported, detail=",".join(unsupported)))
    if unsupported:
        return PipelineResult(
            verdict="block", output_text=compose_refusal("unsupported_claim", language), stages=stages
        )

    stages.append(StageResult("decision", True, detail="allow"))
    return PipelineResult(verdict="allow", output_text=response_text, stages=stages)
