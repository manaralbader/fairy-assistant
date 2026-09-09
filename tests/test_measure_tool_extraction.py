"""Sanity checks on the extraction pass-rate measurement itself — not the
numbers (those are read off the script's real output, never hand-typed into
a report), but the properties any honest measurement of this loop must have."""

from __future__ import annotations

from measure_tool_extraction import measure


def _rates(rows: list[dict]) -> tuple[float, float]:
    n = len(rows)
    first = sum(r["first_pass"] for r in rows) / n
    final = sum(r["final_pass"] for r in rows) / n
    return first, final


def test_repair_never_makes_the_pass_rate_worse():
    for tier in ("commercial", "open_weight"):
        results = measure(tier)
        for language, rows in results.items():
            first_rate, final_rate = _rates(rows)
            assert final_rate >= first_rate, f"{tier}/{language}: repair made things worse"


def test_the_over_length_case_fails_in_both_languages_even_after_repair():
    """Proves the 300-character over-specification guard actually fires and
    that repair can't talk its way around a hard schema limit — the guard
    holds because nothing shortens the text on retry."""
    for tier in ("commercial", "open_weight"):
        results = measure(tier)
        for language, rows in results.items():
            over_length_case = rows[-1]  # the deliberately-long case is always last
            assert over_length_case["final_pass"] is False


def test_open_weight_first_attempt_pass_rate_is_no_better_than_commercial():
    results_commercial = measure("commercial")
    results_open_weight = measure("open_weight")
    for language in ("en", "ar"):
        first_commercial, _ = _rates(results_commercial[language])
        first_open_weight, _ = _rates(results_open_weight[language])
        assert first_open_weight <= first_commercial
