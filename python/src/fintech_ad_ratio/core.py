"""Correction-aware Advance/Decline Ratio reference implementation.

Faithful to the reference algorithm published at The Fintech Builder (topic
``D04-F01-A02``). The metric is exactly:

    advance_decline_ratio = advances / declines

Two design decisions carry almost all of this module's value.

**1. Two independent states, never conflated.** A ratio can fail for two
completely different reasons, and collapsing them loses information:

* ``ratio_state`` describes the **denominator**: ``finite``, ``no_declines``,
  ``no_movers``, ``empty_universe``.
* ``evidence_state`` describes the **input quality**: ``resolved``,
  ``incomplete``, ``ambiguous``, ``unsupported``.

A perfectly clean 2.0 and a 2.0 computed from a universe with 40 halted issues
are both "finite" — but only the first is publishable. So the result carries
*both* ``observed_partition_ratio`` (what the supplied counts actually say,
always populated) and ``advance_decline_ratio`` (populated **only** when
``evidence_state == "resolved"``). A finite-looking number can never silently
hide incomplete coverage.

**2. Zero declines is not infinity.** When ``declines == 0`` the ratio is
undefined, and this implementation reports ``ratio_state="no_declines"`` with a
``None`` value rather than ``inf`` or a sentinel like ``999``. An infinity
propagates through averages and charts and quietly poisons them; an explicit
state does not.

Point-in-time selection works the same way as the rest of the breadth family:
:func:`evaluate_advance_decline_ratio_as_of` considers only snapshots available
at ``decision_as_of``, then requires a contiguous, uniquely-identified,
correctly-linked revision chain. Two records competing for the highest revision
are ``ambiguous`` even if one looks more plausible — correction order is the
source steward's job to repair, not this calculator's to guess.

Note the partition rule is a **hard error**, not a status: if the classification
buckets do not sum exactly to ``universe_size``, the snapshot is structurally
invalid and raises. A count that does not add up is a caller bug, not a data gap.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable, Literal, Mapping, TypedDict


EvidenceState = Literal["resolved", "incomplete", "ambiguous", "unsupported"]
RatioState = Literal["finite", "no_declines", "no_movers", "empty_universe"]
Direction = Literal[
    "advances_dominant",
    "declines_dominant",
    "balanced",
    "advances_only",
    "no_movers",
    "no_universe",
]


class BreadthValidationError(ValueError):
    """Raised when supplied data violates the declared snapshot contract."""


class BreadthResult(TypedDict):
    evidence_state: EvidenceState
    ratio_state: RatioState | None
    advance_decline_ratio: float | None
    direction: Direction | None
    observed_partition_ratio: float | None
    observed_partition_direction: Direction | None
    selected_record_id: str | None
    selected_revision: int | None
    advances: int | None
    declines: int | None
    unchanged: int | None
    excluded_count: int | None
    universe_size: int | None
    mover_count: int | None
    classified_count: int | None
    coverage_ratio: float | None
    is_provisional: bool | None
    metric: Literal["advancing_issues_divided_by_declining_issues"]
    reasons: list[str]


TEXT_FIELDS = (
    "series_id",
    "record_id",
    "venue_id",
    "calendar_id",
    "session_id",
    "universe_id",
    "universe_revision",
    "listing_id_scheme",
    "security_type_policy",
    "comparison_basis",
    "corporate_action_policy",
)
QUERY_POLICY_FIELDS = (
    "calendar_id",
    "session_id",
    "universe_revision",
    "listing_id_scheme",
    "security_type_policy",
    "comparison_basis",
    "corporate_action_policy",
)
COUNT_FIELDS = (
    "advances",
    "declines",
    "unchanged",
    "new_or_no_prior_close",
    "halted",
    "suspended",
    "delisted",
    "missing",
    "unclassified",
    "universe_size",
)
EXCLUSION_FIELDS = (
    "new_or_no_prior_close",
    "halted",
    "suspended",
    "delisted",
    "missing",
    "unclassified",
)
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_SAFE_INTEGER = 9_007_199_254_740_991


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise BreadthValidationError(f"{field} must be a valid YYYY-MM-DD date.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise BreadthValidationError(
            f"{field} must be a valid YYYY-MM-DD date."
        ) from error
    if parsed.isoformat() != value:
        raise BreadthValidationError(f"{field} must use YYYY-MM-DD format.")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        raise BreadthValidationError(f"{field} must be an RFC 3339 timestamp.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise BreadthValidationError(
            f"{field} must be an RFC 3339 timestamp."
        ) from error


def _count(value: Any, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_SAFE_INTEGER
    ):
        raise BreadthValidationError(
            f"{field} must be a non-negative cross-language safe integer."
        )
    return value


def _validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise BreadthValidationError("snapshot must be an object.")
    normalized = dict(snapshot)
    _date(normalized.get("session_date"), "session_date")
    effective = _timestamp(normalized.get("effective_at"), "effective_at")
    available = _timestamp(normalized.get("available_at"), "available_at")
    if available < effective:
        raise BreadthValidationError("available_at cannot precede effective_at.")
    for field in TEXT_FIELDS:
        if not isinstance(normalized.get(field), str) or not normalized[field].strip():
            raise BreadthValidationError(f"{field} must be a non-empty string.")
    predecessor = normalized.get("supersedes_record_id")
    if predecessor is not None and (
        not isinstance(predecessor, str) or not predecessor.strip()
    ):
        raise BreadthValidationError(
            "supersedes_record_id must be null or a non-empty string."
        )
    revision = _count(normalized.get("revision"), "revision")
    if revision < 1:
        raise BreadthValidationError("revision must be at least 1.")
    if not isinstance(normalized.get("is_final"), bool):
        raise BreadthValidationError("is_final must be a boolean.")

    counts = {field: _count(normalized.get(field), field) for field in COUNT_FIELDS}
    partition = sum(counts[field] for field in COUNT_FIELDS if field != "universe_size")
    if partition != counts["universe_size"]:
        raise BreadthValidationError(
            "all classification buckets must sum exactly to universe_size."
        )
    normalized.update(counts)
    return normalized


def calculate_advance_decline_ratio(snapshot: Mapping[str, Any]) -> BreadthResult:
    """Validate one version and calculate the raw advances/declines ratio."""

    item = _validate_snapshot(snapshot)
    advances = item["advances"]
    declines = item["declines"]
    unchanged = item["unchanged"]
    universe_size = item["universe_size"]
    excluded = sum(item[field] for field in EXCLUSION_FIELDS)
    movers = advances + declines
    classified = movers + unchanged
    coverage = classified / universe_size if universe_size else None

    if universe_size == 0:
        ratio_state: RatioState = "empty_universe"
        ratio = None
        direction: Direction = "no_universe"
    elif movers == 0:
        ratio_state = "no_movers"
        ratio = None
        direction = "no_movers"
    elif declines == 0:
        ratio_state = "no_declines"
        ratio = None
        direction = "advances_only"
    else:
        ratio_state = "finite"
        ratio = advances / declines
        direction = (
            "advances_dominant"
            if ratio > 1
            else "declines_dominant"
            if ratio < 1
            else "balanced"
        )

    reasons: list[str] = []
    if not item["is_final"]:
        reasons.append("snapshot_is_provisional")
    if excluded:
        reasons.append("coverage_is_incomplete")
    evidence_state: EvidenceState = "incomplete" if reasons else "resolved"

    publishable_ratio = ratio if evidence_state == "resolved" else None
    publishable_direction = direction if evidence_state == "resolved" else None
    return {
        "evidence_state": evidence_state,
        "ratio_state": ratio_state,
        "advance_decline_ratio": publishable_ratio,
        "direction": publishable_direction,
        "observed_partition_ratio": ratio,
        "observed_partition_direction": direction,
        "selected_record_id": item["record_id"],
        "selected_revision": item["revision"],
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "excluded_count": excluded,
        "universe_size": universe_size,
        "mover_count": movers,
        "classified_count": classified,
        "coverage_ratio": coverage,
        "is_provisional": not item["is_final"],
        "metric": "advancing_issues_divided_by_declining_issues",
        "reasons": reasons,
    }


def _empty_result(state: EvidenceState, reason: str) -> BreadthResult:
    return {
        "evidence_state": state,
        "ratio_state": None,
        "advance_decline_ratio": None,
        "direction": None,
        "observed_partition_ratio": None,
        "observed_partition_direction": None,
        "selected_record_id": None,
        "selected_revision": None,
        "advances": None,
        "declines": None,
        "unchanged": None,
        "excluded_count": None,
        "universe_size": None,
        "mover_count": None,
        "classified_count": None,
        "coverage_ratio": None,
        "is_provisional": None,
        "metric": "advancing_issues_divided_by_declining_issues",
        "reasons": [reason],
    }


def evaluate_advance_decline_ratio_as_of(
    snapshots: Iterable[Mapping[str, Any]], query: Mapping[str, Any]
) -> BreadthResult:
    """Select the highest available revision for one declared market session.

    Future-available versions are ignored. Two eligible records at the highest
    revision are ambiguous even if one looks more plausible; correction order
    must be repaired by the source steward rather than guessed here.
    """

    if not isinstance(query, Mapping):
        raise BreadthValidationError("query must be an object.")
    session_date = _date(query.get("session_date"), "query.session_date")
    decision_time = _timestamp(query.get("decision_as_of"), "query.decision_as_of")
    for field in ("venue_id", "universe_id", "series_id", *QUERY_POLICY_FIELDS):
        if not isinstance(query.get(field), str) or not query[field].strip():
            raise BreadthValidationError(f"query.{field} must be a non-empty string.")

    eligible: list[dict[str, Any]] = []
    for raw in snapshots:
        if not isinstance(raw, Mapping):
            raise BreadthValidationError("each snapshot must be an object.")
        if (
            raw.get("session_date") != session_date
            or raw.get("venue_id") != query["venue_id"]
            or raw.get("universe_id") != query["universe_id"]
            or raw.get("series_id") != query["series_id"]
            or any(raw.get(field) != query[field] for field in QUERY_POLICY_FIELDS)
        ):
            continue
        available = _timestamp(raw.get("available_at"), "available_at")
        if available <= decision_time:
            eligible.append(_validate_snapshot(raw))

    if not eligible:
        return _empty_result("unsupported", "no_snapshot_available_as_of_query")
    if len({item["record_id"] for item in eligible}) != len(eligible):
        return _empty_result("ambiguous", "duplicate_record_id")
    highest = max(item["revision"] for item in eligible)
    by_revision: dict[int, list[dict[str, Any]]] = {}
    for item in eligible:
        by_revision.setdefault(item["revision"], []).append(item)
    if set(by_revision) != set(range(1, highest + 1)):
        return _empty_result("ambiguous", "non_contiguous_revision_chain")
    if any(len(items) != 1 for items in by_revision.values()):
        return _empty_result("ambiguous", "conflicting_highest_revision")
    for revision in range(1, highest + 1):
        current = by_revision[revision][0]
        expected = None if revision == 1 else by_revision[revision - 1][0]["record_id"]
        if current.get("supersedes_record_id") != expected:
            return _empty_result("ambiguous", "broken_supersession_chain")
    return calculate_advance_decline_ratio(by_revision[highest][0])
