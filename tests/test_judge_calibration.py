"""Locks in the rubric's calibration floor: kappa >= 0.6 against the real
human-labeled subset, computed fresh every run — never a hardcoded number."""

from __future__ import annotations

from calibrate_judge import run


def test_kappa_meets_the_rubric_floor():
    result = run()
    assert result["n"] >= 30
    assert result["kappa"] >= 0.6, result["disagreements"]


def test_the_labeled_set_has_real_negative_examples():
    """A calibration run against an all-pass label set can't say anything —
    Cohen's kappa is undefined/meaningless without both classes present in
    real numbers."""
    result = run()
    matrix = result["confusion_matrix"]
    assert matrix["tn"] >= 5
    assert matrix["tp"] >= 5
