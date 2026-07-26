"""Fixture-driven exactness and contract tests for the A/D Ratio.

The dataset's 34 named cases are the cross-language parity anchor: this suite
and the TypeScript suite walk the same file and assert the same fields.
"""

import pytest
from conftest import (
    BASE,
    INVALID_CASES,
    QUERY,
    VALID_CASES,
    VERSION_CASES,
    named_snapshot,
    snapshot_for,
)

from fintech_ad_ratio import (
    BreadthValidationError,
    calculate_advance_decline_ratio,
    evaluate_advance_decline_ratio_as_of,
)


# --------------------------------------------------------------------------- #
# The 34 named fixture cases
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", VALID_CASES, ids=[c["name"] for c in VALID_CASES])
def test_valid_cases(case):
    result = calculate_advance_decline_ratio(snapshot_for(case))
    for key, value in case["expected"].items():
        assert result[key] == value, key


@pytest.mark.parametrize("case", INVALID_CASES, ids=[c["name"] for c in INVALID_CASES])
def test_invalid_cases_raise(case):
    with pytest.raises(BreadthValidationError):
        calculate_advance_decline_ratio(snapshot_for(case))


@pytest.mark.parametrize("case", VERSION_CASES, ids=[c["name"] for c in VERSION_CASES])
def test_version_cases(case):
    snapshots = [named_snapshot(name) for name in case["snapshots"]]
    query = {**QUERY, "decision_as_of": case.get("decision_as_of", QUERY["decision_as_of"])}
    result = evaluate_advance_decline_ratio_as_of(snapshots, query)
    for key, value in case["expected"].items():
        assert result[key] == value, key


# --------------------------------------------------------------------------- #
# The two design decisions this algorithm turns on
# --------------------------------------------------------------------------- #
def test_zero_declines_is_a_state_not_infinity():
    """The headline trap: an undefined ratio must not become inf or a sentinel."""
    result = calculate_advance_decline_ratio({**BASE, "advances": 90, "declines": 0})
    assert result["ratio_state"] == "no_declines"
    assert result["advance_decline_ratio"] is None
    assert result["observed_partition_ratio"] is None
    assert result["direction"] == "advances_only"
    assert result["evidence_state"] == "resolved"  # the data is fine; the ratio isn't


def test_evidence_state_and_ratio_state_are_independent():
    """A finite ratio with poor coverage must not be publishable."""
    poor = calculate_advance_decline_ratio({**BASE, "advances": 50, "declines": 25, "unchanged": 5, "halted": 20})
    assert poor["ratio_state"] == "finite"          # the denominator is fine
    assert poor["evidence_state"] == "incomplete"   # the evidence is not
    assert poor["advance_decline_ratio"] is None    # so nothing is published
    assert poor["observed_partition_ratio"] == 2.0  # but the observation is still visible
    assert "coverage_is_incomplete" in poor["reasons"]


def test_observed_ratio_is_always_reported_even_when_unpublishable():
    result = calculate_advance_decline_ratio({**BASE, "is_final": False})
    assert result["is_provisional"] is True
    assert result["evidence_state"] == "incomplete"
    assert result["advance_decline_ratio"] is None
    assert result["observed_partition_ratio"] == 2.0
    assert result["observed_partition_direction"] == "advances_dominant"
    assert "snapshot_is_provisional" in result["reasons"]


def test_clean_snapshot_publishes_the_ratio():
    result = calculate_advance_decline_ratio(BASE)
    assert result["evidence_state"] == "resolved"
    assert result["advance_decline_ratio"] == result["observed_partition_ratio"] == 2.0
    assert result["direction"] == "advances_dominant"
    assert result["reasons"] == []


def test_zero_advances_is_finite_not_a_special_state():
    """0/90 is a legitimate 0.0 — only a zero *denominator* is undefined."""
    result = calculate_advance_decline_ratio({**BASE, "advances": 0, "declines": 90})
    assert result["ratio_state"] == "finite"
    assert result["advance_decline_ratio"] == 0.0
    assert result["direction"] == "declines_dominant"


# --------------------------------------------------------------------------- #
# Partition, coverage, and the raise-vs-status split
# --------------------------------------------------------------------------- #
def test_partition_mismatch_raises_rather_than_returning_a_status():
    """Counts that do not add up are a caller bug, not a data gap."""
    with pytest.raises(BreadthValidationError):
        calculate_advance_decline_ratio({**BASE, "universe_size": 99})


def test_coverage_ratio_is_classified_over_universe():
    result = calculate_advance_decline_ratio(BASE)
    assert result["classified_count"] == 100
    assert result["coverage_ratio"] == 1.0
    partial = calculate_advance_decline_ratio({**BASE, "unchanged": 0, "halted": 10})
    assert partial["classified_count"] == 90
    assert partial["coverage_ratio"] == 0.9
    assert partial["excluded_count"] == 10


def test_excluded_count_sums_every_exclusion_bucket():
    result = calculate_advance_decline_ratio(
        {**BASE, "unchanged": 4, "halted": 2, "suspended": 1, "delisted": 1, "missing": 1, "unclassified": 1}
    )
    assert result["excluded_count"] == 6
    assert result["advances"] + result["declines"] + result["unchanged"] + result["excluded_count"] == 100


def test_empty_universe_and_no_movers_are_distinct():
    empty = calculate_advance_decline_ratio(
        {**BASE, "advances": 0, "declines": 0, "unchanged": 0, "universe_size": 0}
    )
    assert empty["ratio_state"] == "empty_universe"
    assert empty["direction"] == "no_universe"
    assert empty["coverage_ratio"] is None

    still = calculate_advance_decline_ratio({**BASE, "advances": 0, "declines": 0, "unchanged": 100})
    assert still["ratio_state"] == "no_movers"
    assert still["direction"] == "no_movers"
    assert still["coverage_ratio"] == 1.0


# --------------------------------------------------------------------------- #
# Point-in-time selection
# --------------------------------------------------------------------------- #
def test_a_later_correction_cannot_change_an_earlier_decision():
    snapshots = [named_snapshot("base"), named_snapshot("correction")]
    before = evaluate_advance_decline_ratio_as_of(
        snapshots, {**QUERY, "decision_as_of": "2026-01-05T21:30:00Z"}
    )
    after = evaluate_advance_decline_ratio_as_of(
        snapshots, {**QUERY, "decision_as_of": "2026-01-06T10:00:00Z"}
    )
    assert before["selected_revision"] == 1 and before["advance_decline_ratio"] == 2.0
    assert after["selected_revision"] == 2 and after["advance_decline_ratio"] == 58 / 32


def test_a_competing_highest_revision_is_ambiguous_not_a_guess():
    result = evaluate_advance_decline_ratio_as_of(
        [named_snapshot("base"), named_snapshot("correction"), named_snapshot("conflict")], QUERY
    )
    assert result["evidence_state"] == "ambiguous"
    assert result["advance_decline_ratio"] is None
    assert result["reasons"] == ["conflicting_highest_revision"]


def test_snapshots_for_another_universe_or_policy_are_not_selected():
    for name in ("other_universe", "different_policy"):
        result = evaluate_advance_decline_ratio_as_of([named_snapshot(name)], QUERY)
        assert result["evidence_state"] == "unsupported", name
        assert result["advance_decline_ratio"] is None


def test_nothing_available_yet_is_unsupported():
    result = evaluate_advance_decline_ratio_as_of(
        [named_snapshot("base")], {**QUERY, "decision_as_of": "2026-01-05T21:04:59Z"}
    )
    assert result["evidence_state"] == "unsupported"
    assert result["reasons"] == ["no_snapshot_available_as_of_query"]


def test_a_future_malformed_snapshot_does_not_leak_into_an_earlier_query():
    """Records past the decision time must not even be validated."""
    result = evaluate_advance_decline_ratio_as_of(
        [named_snapshot("base"), named_snapshot("future_malformed")],
        {**QUERY, "decision_as_of": "2026-01-05T21:30:00Z"},
    )
    assert result["evidence_state"] == "resolved"
    assert result["selected_revision"] == 1


def test_query_requires_every_policy_field():
    for field in QUERY:
        if field == "decision_as_of":
            continue
        broken = {**QUERY, field: ""}
        with pytest.raises(BreadthValidationError):
            evaluate_advance_decline_ratio_as_of([named_snapshot("base")], broken)


def test_result_reports_the_selected_record_for_audit():
    result = evaluate_advance_decline_ratio_as_of(
        [named_snapshot("base"), named_snapshot("correction")], QUERY
    )
    assert result["selected_record_id"] == "SYNTH-2026-01-05-R2"
    assert result["selected_revision"] == 2
    assert result["metric"] == "advancing_issues_divided_by_declining_issues"
