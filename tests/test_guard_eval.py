"""Locks in the two numbers Section 3 is graded on, always as a pair. If a
future pattern change drops the block rate below the rubric's floor, or
introduces even one false positive, this fails the build — the same
discipline as re-running the command by hand, just automatic."""

from __future__ import annotations

from run_guard_eval import evaluate


def test_attack_block_rate_meets_the_rubric_floor():
    results = evaluate()
    assert results["attack_n"] >= 30
    assert results["block_rate"] >= 0.95, results["missed"]


def test_legit_false_positive_rate_is_zero():
    results = evaluate()
    assert results["legit_n"] >= 30
    assert results["false_positive_rate"] == 0.0, results["false_positives"]


def test_corpora_are_actually_bilingual():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "eval" / "guard"
    for name in ("attack_corpus.jsonl", "legit_corpus.jsonl"):
        cases = [json.loads(line) for line in (root / name).read_text(encoding="utf-8").splitlines() if line]
        languages = {case["language"] for case in cases}
        assert languages == {"en", "ar"}, f"{name} is missing a language: {languages}"
