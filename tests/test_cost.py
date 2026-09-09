from __future__ import annotations

from measure_cost import check_near_miss_suite, run_traffic


def test_near_miss_suite_has_zero_wrong_hits():
    assert check_near_miss_suite() == []


def test_caching_cuts_cost_by_at_least_60_percent():
    before = run_traffic(use_cache=False)
    after = run_traffic(use_cache=True)
    reduction = 1 - (after.total_cost_usd / before.total_cost_usd)
    assert reduction >= 0.60


def test_prompt_cache_hit_rate_meets_the_rubric_floor():
    after = run_traffic(use_cache=True)
    assert after.cache_hit_rate >= 0.65


def test_meter_covers_every_call():
    before = run_traffic(use_cache=False)
    assert before.call_count == 36  # 6 unique FAQs x 6 repeats, all metered
