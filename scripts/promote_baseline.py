"""Promotes a clean run's per-slice pass rates to eval/baseline.json — the
file the regression gate compares every future run against. Deliberately
tracked in git (unlike eval/out/*.json run artefacts): the gate needs it to
exist without re-running anything.

Promotion is a deliberate, diffable act, never automatic — run this by hand
and commit the result with a message saying why.

    python scripts/promote_baseline.py [commercial|open_weight]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import run_all  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fairy.eval.gate import slice_rates  # noqa: E402

BASELINE_PATH = Path(__file__).resolve().parent.parent / "eval" / "baseline.json"


def promote(tier: str = "commercial") -> dict:
    results = run_all(tier)
    baseline = slice_rates(results)
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return baseline


if __name__ == "__main__":
    tier_arg = sys.argv[1] if len(sys.argv) > 1 else "commercial"
    result = promote(tier_arg)
    print(f"wrote {BASELINE_PATH} from a clean '{tier_arg}' run:")
    print(json.dumps(result, indent=2, sort_keys=True))
