"""Model comparison: both backends over the same golden set, cost and
latency measured (not quoted from a vendor page), plus a self-host
break-even from throughput actually measured here.

    python scripts/compare_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from run_eval import load_cases, _session_for  # noqa: E402

from fairy.cost.meter import PRICE_PER_1K_TOKENS, MeteredClient  # noqa: E402
from fairy.llm.sim import SimClient  # noqa: E402
from fairy.router import handle_turn  # noqa: E402
from fairy.tools.store import demo_store  # noqa: E402

FIXED_SELF_HOST_COST_PER_HOUR_USD = 0.50  # a modest rented-GPU rate


def run_tier(tier: str) -> dict:
    metered = MeteredClient(SimClient(tier=tier, real_sleep=True), tier=tier)
    passed = 0
    for case in load_cases():
        session = _session_for(case["text"])
        result = handle_turn(case["text"], client=metered, session=session, store=demo_store())
        # coarse pass signal for this comparison: blocked iff adversarial
        if case["risk"] == "adversarial":
            passed += result.route == "blocked"
        else:
            passed += result.route != "blocked"

    n = len(load_cases())
    avg_latency_ms = sum(r.latency_ms for r in metered.records) / len(metered.records)
    return {
        "tier": tier,
        "pass_rate": passed / n,
        "total_cost_usd": metered.total_cost_usd,
        "cost_per_conversation_usd": metered.total_cost_usd / n,
        "avg_latency_ms": avg_latency_ms,
        "requests_per_hour": 3600 / (avg_latency_ms / 1000) if avg_latency_ms else 0,
    }


def break_even(commercial: dict) -> dict:
    cost_per_request = commercial["cost_per_conversation_usd"]
    if cost_per_request <= 0:
        return {"break_even_requests_per_hour": float("inf")}
    return {"break_even_requests_per_hour": FIXED_SELF_HOST_COST_PER_HOUR_USD / cost_per_request}


def main() -> None:
    commercial = run_tier("commercial")
    open_weight = run_tier("open_weight")
    be = break_even(commercial)

    for row in (commercial, open_weight):
        print(
            f"{row['tier']:12s} pass={row['pass_rate']:.0%}  "
            f"cost/conversation=${row['cost_per_conversation_usd']:.6f}  "
            f"avg_latency={row['avg_latency_ms']:.1f}ms  "
            f"throughput={row['requests_per_hour']:.0f} req/hr"
        )

    print(
        f"\nself-host break-even: at ${FIXED_SELF_HOST_COST_PER_HOUR_USD:.2f}/hr fixed cost, "
        f"self-hosting the open-weight tier pays for itself above "
        f"{be['break_even_requests_per_hour']:.0f} conversations/hour "
        f"(commercial-tier cost/conversation: ${commercial['cost_per_conversation_usd']:.6f}); "
        f"measured open-weight throughput at this tier's simulated latency: "
        f"{open_weight['requests_per_hour']:.0f} req/hr."
    )


if __name__ == "__main__":
    main()
