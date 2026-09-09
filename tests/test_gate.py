"""The regression gate itself: a clean run must pass against the tracked
baseline, and the seeded regression (fairy.llm.sim's strict_grounding=False,
standing in for prompts/library/answer_faq/v2.md) must fail it — on a named
slice, not just "somewhere."""

from __future__ import annotations

import json
from pathlib import Path

from run_eval import run_all

from fairy.eval.gate import check_gate

BASELINE_PATH = Path(__file__).resolve().parent.parent / "eval" / "baseline.json"


def _baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_a_clean_run_passes_the_gate():
    result = check_gate(run_all("commercial", strict_grounding=True), _baseline())
    assert result.passed, result.regressions


def test_the_seeded_regression_fails_the_gate_on_the_faq_slice():
    result = check_gate(run_all("commercial", strict_grounding=False), _baseline())
    assert not result.passed
    assert any("intent=faq" in regression for regression in result.regressions)


def test_the_seeded_regression_does_not_touch_the_safety_stratum():
    """The regression is specifically about grounding refusal quality, not
    a guard bypass — safety should stay untouched even while the gate fails
    elsewhere, which is exactly what "read slices, not the average" means."""
    results = run_all("commercial", strict_grounding=False)
    safety = [r for r in results if r["risk"] == "adversarial"]
    assert all(r["passed"] for r in safety)
