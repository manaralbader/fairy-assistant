"""Calibrates the rule-based judge (fairy.eval.judge) against a real
human-labeled subset: prints a confusion matrix and Cohen's kappa. Rerunnable
and diffable — this is the source of any judge-calibration number that ends
up in EVALUATION_REPORT.md. If kappa drops below the rubric's 0.6 floor, the
judge needs fixing before it gates anything, not the labels.

    python scripts/calibrate_judge.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fairy.eval.judge import judge_response  # noqa: E402

LABELS_PATH = Path(__file__).resolve().parent.parent / "eval" / "judge" / "human_labels.jsonl"


def load_labels() -> list[dict]:
    with LABELS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def cohens_kappa(human: list[str], judge: list[str]) -> tuple[float, dict[str, int]]:
    n = len(human)
    matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}  # from the judge's point of view, "pass" == positive
    for h, j in zip(human, judge):
        if h == "pass" and j == "pass":
            matrix["tp"] += 1
        elif h == "fail" and j == "fail":
            matrix["tn"] += 1
        elif h == "fail" and j == "pass":
            matrix["fp"] += 1
        else:
            matrix["fn"] += 1

    observed_agreement = (matrix["tp"] + matrix["tn"]) / n
    human_pass_rate = human.count("pass") / n
    judge_pass_rate = judge.count("pass") / n
    chance_agreement = human_pass_rate * judge_pass_rate + (1 - human_pass_rate) * (1 - judge_pass_rate)
    if chance_agreement == 1.0:
        kappa = 1.0
    else:
        kappa = (observed_agreement - chance_agreement) / (1 - chance_agreement)
    return kappa, matrix


def run() -> dict:
    cases = load_labels()
    human = [case["human_label"] for case in cases]
    judge = [judge_response(case["response"]) for case in cases]
    kappa, matrix = cohens_kappa(human, judge)
    disagreements = [
        case for case, h, j in zip(cases, human, judge) if h != j
    ]
    return {"n": len(cases), "kappa": kappa, "confusion_matrix": matrix, "disagreements": disagreements}


def report(result: dict) -> str:
    lines = [
        f"n={result['n']}  Cohen's kappa={result['kappa']:.2f}",
        f"confusion matrix (human x judge): {result['confusion_matrix']}",
    ]
    if result["disagreements"]:
        lines.append("disagreements:")
        for case in result["disagreements"]:
            note = f" — {case['note']}" if "note" in case else ""
            lines.append(f"  {case['id']}: human={case['human_label']}{note}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(run()))
