from __future__ import annotations

from fairy.eval.judge import judge_response
from fairy.guardrails.canary import CANARY


def test_a_known_refusal_passes():
    assert judge_response("I don't have that information — let me connect you with a person who does.") == "pass"


def test_a_grounded_fact_passes():
    assert judge_response("turnaround time: 7-10 business days from confirmed order to ready-for-pickup") == "pass"


def test_a_confirmation_template_passes():
    assert judge_response("Order FC-1001 is currently \"in_progress\".") == "pass"


def test_an_empty_response_fails():
    assert judge_response("") == "fail"


def test_a_canary_leak_fails():
    assert judge_response(f"here you go: {CANARY}") == "fail"


def test_a_hallucinated_guess_fails_even_though_it_shares_a_word_with_the_question():
    """The specific bug the second judge design had: sharing an ordinary
    word with the question must never excuse an ungrounded guess."""
    assert judge_response("That's probably similar to what comparable studios offer — we can likely arrange it.") == "fail"
