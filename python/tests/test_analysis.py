"""Comparison helpers for an asymmetric metric."""

import math

import pytest
from conftest import BASE

from fintech_ad_ratio import (
    calculate_advance_decline_ratio,
    compare_strength,
    log_ad_ratio,
    percent_advancing,
    strength_key,
)


def result(**patch):
    return calculate_advance_decline_ratio({**BASE, **patch})


def test_log_ratio_is_symmetric_where_the_raw_ratio_is_not():
    """2.0 and 0.5 are mirror-image days; raw distance from 1.0 says otherwise."""
    up = result(advances=60, declines=30)      # ratio 2.0, +1.0 from neutral
    down = result(advances=30, declines=60)    # ratio 0.5, -0.5 from neutral
    assert up["advance_decline_ratio"] == 2.0
    assert down["advance_decline_ratio"] == 0.5
    # Raw ratios are asymmetric around 1.0 ...
    assert abs(up["advance_decline_ratio"] - 1) != abs(down["advance_decline_ratio"] - 1)
    # ... but their logs are exactly symmetric around 0.
    assert log_ad_ratio(up) == pytest.approx(math.log(2))
    assert log_ad_ratio(down) == pytest.approx(-math.log(2))
    assert log_ad_ratio(up) + log_ad_ratio(down) == pytest.approx(0.0, abs=1e-12)


def test_balanced_day_has_zero_log_ratio():
    assert log_ad_ratio(result(advances=45, declines=45)) == pytest.approx(0.0)


def test_percent_advancing_is_bounded_and_survives_zero_declines():
    assert percent_advancing(result(advances=60, declines=30)) == pytest.approx(2 / 3)
    # Where the raw ratio is undefined, percent advancing is a clean 1.0.
    no_declines = result(advances=90, declines=0)
    assert no_declines["advance_decline_ratio"] is None
    assert percent_advancing(no_declines) == 1.0
    assert percent_advancing(result(advances=0, declines=90)) == 0.0


def test_log_ratio_is_none_where_it_would_be_infinite():
    assert log_ad_ratio(result(advances=90, declines=0)) is None   # would be +inf
    assert log_ad_ratio(result(advances=0, declines=90)) is None   # would be -inf


def test_helpers_refuse_unresolved_evidence():
    provisional = result(is_final=False)
    assert provisional["evidence_state"] == "incomplete"
    assert log_ad_ratio(provisional) is None
    assert percent_advancing(provisional) is None
    assert strength_key(provisional) is None


def test_no_declines_ranks_above_every_finite_ratio():
    """Naive sorting on a None ratio would rank the strongest day as missing."""
    huge = result(advances=89, declines=1)     # ratio 89.0
    perfect = result(advances=90, declines=0)  # nothing declined at all
    assert compare_strength(perfect, huge) == "stronger"
    assert compare_strength(huge, perfect) == "weaker"


def test_compare_strength_orders_finite_ratios():
    strong = result(advances=60, declines=30)
    weak = result(advances=30, declines=60)
    assert compare_strength(strong, weak) == "stronger"
    assert compare_strength(weak, strong) == "weaker"
    assert compare_strength(strong, result(advances=60, declines=30)) == "equal"


def test_directionless_states_are_incomparable_not_zero():
    still = result(advances=0, declines=0, unchanged=100)
    assert still["ratio_state"] == "no_movers"
    assert compare_strength(still, result()) == "incomparable"
    assert strength_key(still) is None


def test_sorting_a_mixed_day_list_puts_the_strongest_last():
    days = [
        result(advances=30, declines=60),   # 0.5
        result(advances=90, declines=0),    # no_declines -> strongest
        result(advances=60, declines=30),   # 2.0
    ]
    ranked = sorted(days, key=strength_key)
    assert [d["ratio_state"] for d in ranked] == ["finite", "finite", "no_declines"]
    assert [d["advance_decline_ratio"] for d in ranked[:2]] == [0.5, 2.0]
