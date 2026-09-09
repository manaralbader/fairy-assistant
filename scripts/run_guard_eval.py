"""Runs the input-side guard (stages 1-2 of fairy.guardrails.pipeline) over
the attack and legitimate corpora and reports the two numbers that always
have to be quoted together: block rate on attacks, false-positive rate on
legitimate traffic. Rerunnable and diffable — this is the source of any guard
number that ends up in BENCHMARKS.md.

    python scripts/run_guard_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fairy.guardrails.pipeline import check_input  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ATTACK_CORPUS = ROOT / "eval" / "guard" / "attack_corpus.jsonl"
LEGIT_CORPUS = ROOT / "eval" / "guard" / "legit_corpus.jsonl"


def _load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate() -> dict:
    attacks = _load(ATTACK_CORPUS)
    legit = _load(LEGIT_CORPUS)

    blocked_attacks = []
    missed_attacks = []
    for case in attacks:
        result = check_input(case["text"])
        (blocked_attacks if result is not None else missed_attacks).append(case)

    false_positives = []
    for case in legit:
        result = check_input(case["text"])
        if result is not None:
            false_positives.append(case)

    return {
        "attack_n": len(attacks),
        "blocked": len(blocked_attacks),
        "missed": missed_attacks,
        "block_rate": len(blocked_attacks) / len(attacks),
        "legit_n": len(legit),
        "false_positive_n": len(false_positives),
        "false_positives": false_positives,
        "false_positive_rate": len(false_positives) / len(legit),
    }


def report(results: dict) -> str:
    lines = [
        f"attack corpus:  n={results['attack_n']}  blocked={results['blocked']}  "
        f"block_rate={results['block_rate']:.1%}",
    ]
    if results["missed"]:
        lines.append("  missed attacks:")
        for case in results["missed"]:
            lines.append(f"    {case['id']} [{case['category']}]: {case['text'][:60]}")
    lines.append(
        f"legit corpus:   n={results['legit_n']}  false_positives={results['false_positive_n']}  "
        f"false_positive_rate={results['false_positive_rate']:.1%}"
    )
    if results["false_positives"]:
        lines.append("  false positives:")
        for case in results["false_positives"]:
            lines.append(f"    {case['id']} [trap={case.get('trap')}]: {case['text'][:60]}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(evaluate()))
