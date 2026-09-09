"""Before/after cost measurement: repeated FAQ traffic (customers really do
ask the same handful of questions over and over) through the metered router,
once with no caching and once with prompt-cache + response-cache both on.
Also runs the near-miss suite that picked the semantic cache's threshold.

    python scripts/measure_cost.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fairy.cost.meter import MeteredClient  # noqa: E402
from fairy.cost.response_cache import ResponseCache  # noqa: E402
from fairy.llm.sim import SimClient  # noqa: E402
from fairy.router import handle_turn  # noqa: E402
from fairy.tools.session import Session  # noqa: E402
from fairy.tools.store import demo_store  # noqa: E402

FAQ_TRAFFIC = [
    "What is the turnaround time for a custom piece?",
    "What materials do you use for the beads?",
    "How much does a small piece cost?",
    "What are your opening hours?",
    "قديش وقت التنفيذ للقطعة المخصصة؟",
    "شو المواد التي تستخدموها في القطع؟",
] * 6  # a repeat-traffic pattern: the same handful of FAQs asked over and over

NEAR_MISS_SUITE = [
    ("What is the turnaround time for a custom piece?", "What's the turnaround time for a custom piece?", True),
    ("What materials do you use for the beads?", "What materials do you use?", True),
    ("How much does a small piece cost?", "How much is a small piece?", True),
    ("What is the turnaround time for a custom piece?", "What are your opening hours?", False),
    ("What materials do you use for the beads?", "How much does a small piece cost?", False),
    ("Do you ship to other countries?", "Do you offer engraving on the beads?", False),
]


def run_traffic(*, use_cache: bool) -> MeteredClient:
    client = SimClient(tier="commercial")
    metered = MeteredClient(client, tier="commercial")
    cache = ResponseCache() if use_cache else None
    session = Session()
    store = demo_store()
    for text in FAQ_TRAFFIC:
        handle_turn(text, client=metered, session=session, store=store, response_cache=cache)
    return metered


def check_near_miss_suite(threshold: float = 0.6) -> list[str]:
    cache = ResponseCache(semantic_threshold=threshold)
    wrong_hits = []
    for query_a, query_b, should_hit in NEAR_MISS_SUITE:
        cache.set(query_a, "en", f"ANSWER_FOR::{query_a}")
        result = cache.get(query_b, "en")
        did_hit = result is not None
        if did_hit != should_hit:
            wrong_hits.append(f"{query_a!r} vs {query_b!r}: expected hit={should_hit}, got {did_hit}")
        cache._store.clear()
    return wrong_hits


def main() -> None:
    wrong_hits = check_near_miss_suite()
    print(f"near-miss suite: {len(NEAR_MISS_SUITE)} pairs, {len(wrong_hits)} wrong hits")
    for w in wrong_hits:
        print(f"  WRONG: {w}")

    before = run_traffic(use_cache=False)
    after = run_traffic(use_cache=True)

    print(f"\nbefore (no cache): {before.call_count} model calls, "
          f"${before.total_cost_usd:.6f}, cache_hit_rate={before.cache_hit_rate:.1%}")
    print(f"after  (cached):   {after.call_count} model calls, "
          f"${after.total_cost_usd:.6f}, cache_hit_rate={after.cache_hit_rate:.1%}")

    reduction = 1 - (after.total_cost_usd / before.total_cost_usd)
    print(f"\ncost reduction: {reduction:.1%}")


if __name__ == "__main__":
    main()
