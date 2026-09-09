"""Structural checks on the golden set itself — stratification, not
individual case content (that's what test_eval_harness.py checks by
actually running it)."""

from __future__ import annotations

from collections import Counter

from run_eval import load_cases

DIMENSIONS = ("intent", "language", "difficulty", "risk")


def test_at_least_forty_cases():
    assert len(load_cases()) >= 40


def test_every_stratum_value_has_at_least_eight_cases():
    cases = load_cases()
    for dimension in DIMENSIONS:
        counts = Counter(case[dimension] for case in cases)
        for value, n in counts.items():
            assert n >= 8, f"{dimension}={value} only has {n} cases"


def test_arabic_majority():
    cases = load_cases()
    counts = Counter(case["language"] for case in cases)
    assert counts["ar"] > counts["en"]


def test_safety_is_oversampled_relative_to_a_realistic_attack_rate():
    cases = load_cases()
    counts = Counter(case["risk"] for case in cases)
    share = counts["adversarial"] / len(cases)
    assert share >= 0.10  # real attack traffic is nowhere near 10%


def test_every_case_has_a_unique_id():
    cases = load_cases()
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
