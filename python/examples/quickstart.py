"""Quickstart: the A/D Ratio, its two states, and why logs beat raw ratios.

Run:  python examples/quickstart.py
"""

import json
from pathlib import Path

from fintech_ad_ratio import (
    calculate_advance_decline_ratio,
    compare_strength,
    evaluate_advance_decline_ratio_as_of,
    log_ad_ratio,
    percent_advancing,
)

FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ad_ratio_fixtures.json").read_text())
base, named, query = FIXTURE["base_snapshot"], FIXTURE["named_snapshots"], FIXTURE["query"]

# 1) A clean snapshot publishes its ratio.
clean = calculate_advance_decline_ratio(base)
print(f"clean:       evidence={clean['evidence_state']:<10} ratio_state={clean['ratio_state']:<8} "
      f"ratio={clean['advance_decline_ratio']}")

# 2) The same finite ratio, but 20 halted issues -> observable, NOT publishable.
poor = calculate_advance_decline_ratio({**base, "advances": 50, "declines": 25, "unchanged": 5, "halted": 20})
print(f"low cover:   evidence={poor['evidence_state']:<10} ratio_state={poor['ratio_state']:<8} "
      f"ratio={poor['advance_decline_ratio']} (observed {poor['observed_partition_ratio']})")

# 3) Nothing declined: a state, not infinity.
nd = calculate_advance_decline_ratio({**base, "advances": 90, "declines": 0})
print(f"no declines: evidence={nd['evidence_state']:<10} ratio_state={nd['ratio_state']:<8} "
      f"ratio={nd['advance_decline_ratio']}  (percent advancing still {percent_advancing(nd)})")

# 4) Ratios are asymmetric; logs are not.
up = calculate_advance_decline_ratio({**base, "advances": 60, "declines": 30})
down = calculate_advance_decline_ratio({**base, "advances": 30, "declines": 60})
print(f"\nmirror days: {up['advance_decline_ratio']} vs {down['advance_decline_ratio']}  "
      f"-> raw distance from 1.0 differs ({abs(up['advance_decline_ratio']-1)} vs {abs(down['advance_decline_ratio']-1)})")
print(f"             log {log_ad_ratio(up):+.6f} vs {log_ad_ratio(down):+.6f}  -> symmetric")

# 5) Point-in-time: a correction must not rewrite an earlier decision.
snapshots = [base, {**base, **named["correction"]}]
print()
for decision in ("2026-01-05T21:30:00Z", "2026-01-06T10:00:00Z"):
    r = evaluate_advance_decline_ratio_as_of(snapshots, {**query, "decision_as_of": decision})
    print(f"as of {decision}: rev {r['selected_revision']} -> ratio {r['advance_decline_ratio']:.6f}")

# 6) Ranking treats "nothing declined" as the strongest reading, not missing data.
print(f"\nno_declines vs 2.0 -> {compare_strength(nd, clean)}")
