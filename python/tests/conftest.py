"""Shared fixture loading.

The dataset ships 34 named cases in three shapes:

* ``valid_cases``   — a ``patch`` onto ``base_snapshot`` plus expected fields
* ``invalid_cases`` — a ``patch`` and/or a ``remove`` that must raise
* ``version_cases`` — named snapshots (themselves patches onto base) plus a
  ``decision_as_of``, exercising point-in-time selection

Both language suites drive off this same file, which is what makes the
cross-language parity claim real rather than aspirational.
"""

import json
from pathlib import Path

import pytest

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ad_ratio_fixtures.json").read_text())

BASE = FIXTURE["base_snapshot"]
NAMED = FIXTURE["named_snapshots"]
QUERY = FIXTURE["query"]
VALID_CASES = FIXTURE["valid_cases"]
INVALID_CASES = FIXTURE["invalid_cases"]
VERSION_CASES = FIXTURE["version_cases"]


def snapshot_for(case):
    """Apply a case's ``patch`` / ``remove`` to the base snapshot."""
    snapshot = {**BASE, **case.get("patch", {})}
    if "remove" in case:
        snapshot.pop(case["remove"], None)
    return snapshot


def named_snapshot(name):
    """Named snapshots are patches onto base, not standalone records."""
    return BASE if name == "base" else {**BASE, **NAMED[name]}


@pytest.fixture
def base():
    return dict(BASE)
