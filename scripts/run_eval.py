"""Runs the golden set through the real router (fairy.router.handle_turn) —
not a simplified copy — against the default (simulated) backend, and reports
pass/fail overall and sliced by intent, language, difficulty, and risk.
Rerunnable and diffable: this is the source of any evaluation number that
ends up in EVALUATION_REPORT.md.

    python scripts/run_eval.py [commercial|open_weight]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fairy.llm.sim import DONT_KNOW, SimClient  # noqa: E402
from fairy.router import handle_turn  # noqa: E402
from fairy.tools.session import Session  # noqa: E402
from fairy.tools.store import demo_store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET = ROOT / "eval" / "golden" / "golden_set.jsonl"

_ORDER_ID_PATTERN = re.compile(r"FC-\d{4,}")
_ORDER_PHONE = {"FC-1001": "0501234321", "FC-1002": "0509876"}
_DEFAULT_PHONE = "0501234321"


def load_cases() -> list[dict]:
    with GOLDEN_SET.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _session_for(text: str) -> Session:
    match = _ORDER_ID_PATTERN.search(text)
    phone = _ORDER_PHONE.get(match.group(0), _DEFAULT_PHONE) if match else _DEFAULT_PHONE
    session = Session()
    otp = session.request_otp(phone)
    session.authorize(phone, otp)
    return session


def run_case(case: dict, *, tier: str, strict_grounding: bool = True) -> dict:
    client = SimClient(tier=tier, strict_grounding=strict_grounding)
    session = _session_for(case["text"])
    result = handle_turn(case["text"], client=client, session=session, store=demo_store())

    expect = case["expect"]
    checks: list[tuple[str, bool]] = []

    if expect.get("blocked"):
        checks.append(("route_blocked", result.route == "blocked"))
    else:
        if "route" in expect:
            checks.append(("route", result.route == expect["route"]))
        if "must_contain" in expect:
            checks.append(("must_contain", expect["must_contain"] in result.final_text))
        if expect.get("expect_refusal"):
            checks.append(("expect_refusal", result.final_text in DONT_KNOW.values()))
        if "tool" in expect:
            called = bool(result.tool_log) and result.tool_log[0]["tool"] == expect["tool"]
            checks.append(("tool_called", called))
        if "tool_outcome" in expect:
            outcomes = [entry["outcome"] for entry in result.tool_log]
            if expect["tool_outcome"] == "ok":
                # the repair loop is allowed to take more than one attempt —
                # what matters is that it eventually succeeded.
                outcome_ok = "ok" in outcomes
            else:
                # for an expected failure, it must never have quietly
                # succeeded instead, and the expected failure must appear.
                outcome_ok = "ok" not in outcomes and expect["tool_outcome"] in outcomes
            checks.append(("tool_outcome", outcome_ok))

    passed = all(ok for _, ok in checks)
    return {
        "id": case["id"],
        "intent": case["intent"],
        "language": case["language"],
        "difficulty": case["difficulty"],
        "risk": case["risk"],
        "passed": passed,
        "checks": checks,
        "route": result.route,
        "final_text": (result.final_text or "")[:80],
    }


def run_all(tier: str = "commercial", *, strict_grounding: bool = True) -> list[dict]:
    return [run_case(case, tier=tier, strict_grounding=strict_grounding) for case in load_cases()]


def slice_report(results: list[dict], key: str) -> dict[str, tuple[int, int]]:
    buckets: dict[str, list[bool]] = {}
    for r in results:
        buckets.setdefault(r[key], []).append(r["passed"])
    return {value: (sum(flags), len(flags)) for value, flags in buckets.items()}


def report(results: list[dict]) -> str:
    lines = []
    total_passed = sum(r["passed"] for r in results)
    lines.append(f"overall: {total_passed}/{len(results)} ({total_passed / len(results):.1%})")
    for key in ("intent", "language", "difficulty", "risk"):
        lines.append(f"by {key}:")
        for value, (passed, n) in sorted(slice_report(results, key).items()):
            lines.append(f"  {value}: {passed}/{n} ({passed / n:.0%})")
    failed = [r for r in results if not r["passed"]]
    if failed:
        lines.append("failed cases:")
        for r in failed:
            lines.append(f"  {r['id']}: route={r['route']} checks={r['checks']} text={r['final_text']!r}")
    return "\n".join(lines)


if __name__ == "__main__":
    tier_arg = sys.argv[1] if len(sys.argv) > 1 else "commercial"
    print(f"=== tier: {tier_arg} ===")
    print(report(run_all(tier_arg)))
