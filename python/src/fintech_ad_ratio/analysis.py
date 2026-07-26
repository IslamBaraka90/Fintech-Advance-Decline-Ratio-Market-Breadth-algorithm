"""Comparison helpers for a fundamentally asymmetric metric.

The A/D ratio is a **ratio**, and ratios are not symmetric around their neutral
point. "Twice as many advances as declines" is ``2.0``; the mirror-image day —
twice as many declines — is ``0.5``. Those are equally strong readings in
opposite directions, but ``2.0`` sits 1.0 above neutral while ``0.5`` sits only
0.5 below it. Averaging raw ratios, or ranking them, therefore over-weights up
days and compresses down days.

This module supplies the two standard fixes plus a safe comparison:

* :func:`log_ad_ratio` — ``ln(advances / declines)``, which *is* symmetric:
  ``2.0`` and ``0.5`` become ``+0.693`` and ``-0.693``. Average these, not raw
  ratios.
* :func:`percent_advancing` — ``advances / (advances + declines)``, a bounded
  ``[0, 1]`` restatement that is easy to chart and never blows up.
* :func:`compare_strength` — orders two results by breadth strength while
  treating the ``no_declines`` case correctly (it is *stronger* than any finite
  ratio, not missing data).

Every function here takes a result from
:func:`~fintech_ad_ratio.core.calculate_advance_decline_ratio` and returns
``None`` when the underlying evidence does not support a published number —
the same refusal-to-guess rule as the calculator itself.
"""

from __future__ import annotations

import math
from typing import Any, Literal, Mapping

__all__ = ["log_ad_ratio", "percent_advancing", "compare_strength", "strength_key"]

Strength = Literal["stronger", "weaker", "equal", "incomparable"]


def _publishable(result: Mapping[str, Any]) -> bool:
    """Only a resolved result may be turned into a published statistic."""
    return result.get("evidence_state") == "resolved"


def log_ad_ratio(result: Mapping[str, Any]) -> float | None:
    """Return ``ln(advances / declines)`` — the symmetric form of the ratio.

    ``None`` when the evidence is not resolved, or when the log is undefined
    (``no_declines`` gives ``+inf``, ``zero advances`` gives ``-inf``, and
    neither is a number you want in a mean).
    """
    if not _publishable(result):
        return None
    if result.get("ratio_state") != "finite":
        return None
    advances = result.get("advances")
    declines = result.get("declines")
    if not advances or not declines:  # 0 advances -> -inf; guarded here
        return None
    return math.log(advances / declines)


def percent_advancing(result: Mapping[str, Any]) -> float | None:
    """Return ``advances / (advances + declines)`` in ``[0, 1]``.

    Unlike the raw ratio this is bounded and stays defined when
    ``declines == 0`` (it becomes ``1.0``), which makes it the friendlier series
    to chart. ``None`` when unresolved or when there are no movers at all.
    """
    if not _publishable(result):
        return None
    movers = result.get("mover_count")
    advances = result.get("advances")
    if not movers or advances is None:
        return None
    return advances / movers


def strength_key(result: Mapping[str, Any]) -> tuple[int, float] | None:
    """Return a sortable key ordering results from weakest to strongest breadth.

    ``no_declines`` ranks above every finite ratio (nothing declined at all),
    which naive numeric sorting on a ``None`` ratio would get wrong. Returns
    ``None`` for results that cannot be ranked.
    """
    if not _publishable(result):
        return None
    state = result.get("ratio_state")
    if state == "no_declines":
        return (1, math.inf)  # strictly stronger than any finite reading
    if state == "finite":
        ratio = result.get("advance_decline_ratio")
        if ratio is None:
            return None
        return (0, ratio)
    return None  # no_movers / empty_universe carry no direction


def compare_strength(left: Mapping[str, Any], right: Mapping[str, Any]) -> Strength:
    """Compare two results by breadth strength.

    Returns ``"incomparable"`` when either side lacks a publishable, directional
    reading — deliberately, rather than silently treating missing as zero.
    """
    left_key = strength_key(left)
    right_key = strength_key(right)
    if left_key is None or right_key is None:
        return "incomparable"
    if left_key == right_key:
        return "equal"
    return "stronger" if left_key > right_key else "weaker"
