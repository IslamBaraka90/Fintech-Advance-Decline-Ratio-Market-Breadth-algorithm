"""Fintech Advance/Decline Ratio — point-in-time market-breadth ratio.

A small, well-specified, cross-language reference implementation of the A/D
Ratio (``advances / declines``) that keeps **denominator state** and **evidence
quality** as separate, explicit dimensions, never reports infinity when nothing
declined, and never publishes a finite-looking number that hides incomplete
coverage.

Companion article (canonical): https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/advance-decline-ratio/
Catalog topic id: D04-F01-A02  (Domain D04 — Market Breadth and Internals / Family D04-F01 — Advance-Decline Breadth)
"""

from __future__ import annotations

from .analysis import compare_strength, log_ad_ratio, percent_advancing, strength_key
from .core import (
    BreadthResult,
    BreadthValidationError,
    calculate_advance_decline_ratio,
    evaluate_advance_decline_ratio_as_of,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BreadthValidationError",
    "BreadthResult",
    "calculate_advance_decline_ratio",
    "evaluate_advance_decline_ratio_as_of",
    "log_ad_ratio",
    "percent_advancing",
    "strength_key",
    "compare_strength",
]
