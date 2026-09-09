"""Demonstrates the regression gate doing its one job: run the real harness
once clean, once against a deliberately-degraded backend standing in for
prompts/library/answer_faq/v2.md (a seeded regression — see that file's
changelog and docs/adr/002 for why the "prompt change" is expressed as a
matching simulator flag here). Both runs go through the exact same
scripts/run_eval.py the rest of this project uses — no simplified copy.

    python scripts/demo_regression_gate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import report, run_all  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fairy.eval.gate import check_gate  # noqa: E402

BASELINE_PATH = Path(__file__).resolve().parent.parent / "eval" / "baseline.json"


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    print("=== clean run (answer_faq.v1-equivalent: strict_grounding=True) ===")
    clean_results = run_all("commercial", strict_grounding=True)
    print(report(clean_results))
    clean_gate = check_gate(clean_results, baseline)
    print(f"\ngate verdict: {'PASS' if clean_gate.passed else 'FAIL'}")
    for regression in clean_gate.regressions:
        print(f"  - {regression}")

    print("\n=== degraded run (answer_faq.v2, the seeded regression) ===")
    degraded_results = run_all("commercial", strict_grounding=False)
    print(report(degraded_results))
    degraded_gate = check_gate(degraded_results, baseline)
    print(f"\ngate verdict: {'PASS' if degraded_gate.passed else 'FAIL'}")
    for regression in degraded_gate.regressions:
        print(f"  - {regression}")


if __name__ == "__main__":
    main()
