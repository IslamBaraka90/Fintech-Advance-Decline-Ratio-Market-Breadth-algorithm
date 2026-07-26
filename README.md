# Fintech Advance/Decline Ratio — Market Breadth Algorithm

> A canonical, well-specified, **cross-language (Python + TypeScript)** reference
> implementation of the **Advance/Decline Ratio** (`advances ÷ declines`) — built
> around two dimensions most implementations collapse into one: **what the
> denominator is** and **whether the evidence supports publishing at all**. It
> never returns `Infinity` when nothing declined, and never publishes a
> finite-looking number that hides incomplete coverage. Ships an **asymmetry &
> comparison** surface (log ratio, percent advancing, strength ordering).

<p>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="TypeScript" src="https://img.shields.io/badge/typescript-5.7%2B-3178c6">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Tests" src="https://img.shields.io/badge/tests-59%20py%20%2F%2027%20ts-brightgreen">
</p>

**📖 Full article (canonical):** **[Advance/Decline Ratio — The Fintech Builder](https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/advance-decline-ratio/)**

This repository is the runnable, production-oriented companion to that article.
The article teaches the concept; this repo is the code you install and build on.

🧭 **Browse all algorithms:** [Awesome FinTech Algorithms](https://github.com/IslamBaraka90/Fintech-Algorithms-Awesome) — the full index of the library.
🗂️ **This algorithm's domain:** [Market Breadth and Internals](https://thefintechbuilder.com/domains/market-breadth-and-internals/) › **Advance-Decline Breadth**

| | |
|---|---|
| **Catalog topic** | `D04-F01-A02` |
| **Domain** | D04 — Market Breadth and Internals |
| **Family** | D04-F01 — Advance/Decline Breadth |
| **Difficulty** | 1 / 5 |
| **Languages** | Python, TypeScript |
| **Builds on** | [Net Advances](https://github.com/IslamBaraka90/Fintech-Net-Advances-Market-Breadth-algorithm) (same partition, different reduction) |

---

## Table of contents

- [What is the A/D Ratio?](#what-is-the-ad-ratio)
- [The two states, and why they are separate](#the-two-states-and-why-they-are-separate)
- [The division-by-zero trap](#the-division-by-zero-trap)
- [State reference](#state-reference)
- [Why this implementation](#why-this-implementation)
- [Install](#install)
- [Quickstart](#quickstart)
- [Analysis: the asymmetry problem](#analysis-the-asymmetry-problem)
- [Snapshot & result shapes](#snapshot--result-shapes)
- [Point-in-time selection](#point-in-time-selection)
- [API reference](#api-reference)
- [Edge cases & limitations](#edge-cases--limitations)
- [Testing](#testing)
- [Related algorithms](#related-algorithms)
- [License](#license)

---

## What is the A/D Ratio?

```
advance_decline_ratio = advances ÷ declines
```

Where [Net Advances](https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/net-advances/)
subtracts the same two counts, the A/D Ratio divides them. The difference is not
cosmetic: subtraction is **scale-dependent** (`+200` means something different on
a 500-issue universe than a 3,000-issue one), while division is **scale-free** —
`2.0` means "two advancing issues for every decliner" on any universe.

That single change of operator introduces one problem subtraction never has: a
**zero denominator**. Everything difficult about this algorithm follows from it.

## The two states, and why they are separate

A breadth reading can fail in two completely independent ways, and merging them
is the most common bug in breadth code:

| dimension | field | question it answers |
|---|---|---|
| denominator | `ratio_state` | *Is the arithmetic even defined?* |
| evidence | `evidence_state` | *Is the input good enough to publish?* |

They are orthogonal. A snapshot can have a perfectly well-defined ratio and
unusable evidence:

```python
poor = calculate_advance_decline_ratio(
    {**snapshot, "advances": 50, "declines": 25, "unchanged": 5, "halted": 20}
)

poor["ratio_state"]              # "finite"      <- the arithmetic is fine
poor["evidence_state"]           # "incomplete"  <- the evidence is not
poor["advance_decline_ratio"]    # None          <- so nothing is published
poor["observed_partition_ratio"] # 2.0           <- but the observation is still visible
poor["reasons"]                  # ["coverage_is_incomplete"]
```

Note the third and fourth lines. The published field is `None`, but the raw
observation is **still reported** under a differently-named field. You are never
denied the number — you are denied the ability to mistake it for a supported one.
20 % of the universe was halted; that 2.0 describes 80 % of the market wearing
the label of all of it.

## The division-by-zero trap

When `declines == 0`, the ratio is **undefined**. The three usual workarounds are
all wrong, and each fails somewhere different:

| workaround | what breaks |
|---|---|
| `advances / max(declines, 1)` | invents a decliner; a 90-issue rally silently becomes exactly `90.0` |
| return `Infinity` / `1e9` | poisons every downstream mean, EMA, and chart axis |
| return `0` or `null` with no state | indistinguishable from "nothing moved" — the *opposite* reading |

This implementation makes it a **first-class state** instead:

```python
r = calculate_advance_decline_ratio({**snapshot, "advances": 90, "declines": 0})

r["ratio_state"]            # "no_declines"
r["advance_decline_ratio"]  # None
r["direction"]              # "advances_only"
r["evidence_state"]         # "resolved"   <- the DATA is fine; the RATIO isn't
```

That last line is the point. `no_declines` is not a data-quality problem — it's
a maximally bullish day the ratio scale simply cannot express. Callers who need
a number anyway have [`percent_advancing`](#analysis-the-asymmetry-problem),
which is bounded and returns `1.0` here.

Note the asymmetry: **zero advances is not a special state.** `0 / 90` is a
legitimate `0.0` with `ratio_state: "finite"`. Only a zero *denominator* is
undefined.

## State reference

**`ratio_state`** — the denominator:

| value | meaning | `advance_decline_ratio` |
|---|---|---|
| `finite` | both counts usable | the number (may be `0.0`) |
| `no_declines` | advances > 0, declines == 0 | `null` — undefined, not infinite |
| `no_movers` | complete universe, nothing moved | `null` — no ratio to form |
| `empty_universe` | the declared universe is empty | `null` |

**`evidence_state`** — the input quality:

| value | meaning |
|---|---|
| `resolved` | final snapshot, full coverage — publishable |
| `incomplete` | provisional and/or excluded issues — observable, not publishable |
| `ambiguous` | two records compete for the highest revision |
| `unsupported` | nothing was causally available at the as-of time |

`advance_decline_ratio` is populated **only** when `evidence_state == "resolved"`
*and* `ratio_state == "finite"`. `observed_partition_ratio` is populated whenever
the arithmetic is defined, regardless of evidence.

## Why this implementation

- **Two independent states**, so "undefined ratio" and "untrustworthy input" can
  never be confused for one another.
- **The observation is never hidden** — `observed_partition_ratio` and
  `observed_partition_direction` report what the data said even when it is
  unpublishable, with `reasons` explaining the gap.
- **Raise vs. status is deliberate.** Counts that don't sum to `universe_size`
  **raise** `BreadthValidationError` — that's a caller bug. Missing evidence
  returns a **state** — that's a data gap.
- **Point-in-time selection** with contiguous-revision-chain validation; a later
  correction cannot change an earlier decision.
- **Cross-language parity** — 34 named fixture cases in one shared JSON file,
  walked field-by-field by *both* suites.

## Install

**Python**

```bash
pip install fintech-ad-ratio
```

**TypeScript / JavaScript (Node ≥ 20)**

```bash
npm install fintech-ad-ratio
```

## Quickstart

**Python**

```python
from fintech_ad_ratio import calculate_advance_decline_ratio

r = calculate_advance_decline_ratio(snapshot)

if r["advance_decline_ratio"] is not None:
    publish(r["advance_decline_ratio"])
elif r["ratio_state"] == "no_declines":
    publish_label("advances only")          # not infinity, not an error
else:
    flag(r["evidence_state"], r["reasons"]) # observed value still in r["observed_partition_ratio"]
```

**TypeScript**

```ts
import { calculateAdvanceDeclineRatio } from "fintech-ad-ratio";

const r = calculateAdvanceDeclineRatio(snapshot);
if (r.advance_decline_ratio !== null) publish(r.advance_decline_ratio);
```

## Analysis: the asymmetry problem

This repo's "beyond the tutorial" surface. The raw ratio has a geometry problem
that bites the moment you average, chart, or rank it:

> Twice as many advancers gives `2.0` — a distance of **1.0** above neutral.
> Twice as many decliners gives `0.5` — a distance of only **0.5** below it.

Two mirror-image days are *not* mirror-image numbers. Average a week of ratios
and the up-days dominate purely as an artifact of the scale. Four helpers fix it:

| helper | returns | why |
|---|---|---|
| `log_ad_ratio` | `ln(A/D)` | symmetric around `0`; mirror days are exact negatives |
| `percent_advancing` | `A / (A+D)` | bounded `[0, 1]`; **defined at `no_declines`** (`1.0`) |
| `strength_key` | sort key | ranks `no_declines` above every finite ratio |
| `compare_strength` | `stronger` / `weaker` / `equal` / `incomparable` | pairwise, without inventing an order |

```python
from fintech_ad_ratio import log_ad_ratio, percent_advancing

log_ad_ratio(up)   # +0.693147   (A/D = 2.0)
log_ad_ratio(down) # -0.693147   (A/D = 0.5)  -> exactly symmetric
```

Two rules run through all four: they return `None` unless
`evidence_state == "resolved"` (an unpublishable ratio stays unpublishable after
a transform), and directionless states (`no_movers`, `empty_universe`) are
**`incomparable`** rather than being flattened to zero — "nothing moved" is not
weaker than an advancing day, it is off the axis entirely.

## Snapshot & result shapes

**Snapshot** — a single point-in-time breadth record:

- *Identity:* `series_id`, `record_id`, `revision`, `supersedes_record_id`,
  `venue_id`, `session_date`, `session_id`, `calendar_id`
- *Policy:* `universe_id`, `universe_revision`, `listing_id_scheme`,
  `security_type_policy`, `comparison_basis`, `corporate_action_policy`
- *Timing:* `effective_at`, `available_at`, `is_final`
- *Counts:* `advances`, `declines`, `unchanged`, `universe_size`, plus the
  exclusion buckets `new_or_no_prior_close`, `halted`, `suspended`, `delisted`,
  `missing`, `unclassified`

The partition invariant is enforced as a hard error:

```
advances + declines + unchanged + (all exclusion buckets) == universe_size
```

**Result:** `evidence_state`, `ratio_state`, `advance_decline_ratio`,
`direction`, `observed_partition_ratio`, `observed_partition_direction`,
`selected_record_id`, `selected_revision`, the counts, `universe_size`,
`mover_count`, `classified_count`, `coverage_ratio`, `excluded_count`,
`is_provisional`, `metric`, and `reasons`.

`direction` is one of `advances_dominant`, `declines_dominant`, `balanced`,
`advances_only`, `no_movers`, `no_universe`.

## Point-in-time selection

Breadth records get **corrected**. `evaluate_advance_decline_ratio_as_of` takes
the whole set of snapshots and a query, and selects only what was genuinely
available:

```python
r = evaluate_advance_decline_ratio_as_of(snapshots, {**query, "decision_as_of": t})
```

The bundled example replays one session across a correction — identical output in
both languages:

```
as of 2026-01-05T21:30:00Z: rev 1 -> ratio 2.000000
as of 2026-01-06T10:00:00Z: rev 2 -> ratio 1.812500
```

Same session, same date: the ratio "moved" because a correction landed, not
because the market did. Four rules make that safe:

1. Snapshots with `available_at > decision_as_of` are **not even validated** — a
   future malformed record cannot break an earlier query.
2. Every policy field must match the query, or the record is `unsupported`. A
   different `universe_revision` is a different measurement.
3. The revision chain must be contiguous and correctly linked
   (`supersedes_record_id`) — gaps are `ambiguous`.
4. Two records competing for the highest revision are `ambiguous`, even if one
   looks more plausible. Repairing correction order is the source steward's job,
   not the calculator's to guess.

## API reference

| Purpose | Python | TypeScript |
|---|---|---|
| Calculate one snapshot | `calculate_advance_decline_ratio(s)` | `calculateAdvanceDeclineRatio(s)` |
| Point-in-time selection | `evaluate_advance_decline_ratio_as_of(s, q)` | `evaluateAdvanceDeclineRatioAsOf(s, q)` |
| Symmetric log ratio | `log_ad_ratio(r)` | `logAdRatio(r)` |
| Bounded participation | `percent_advancing(r)` | `percentAdvancing(r)` |
| Sort key | `strength_key(r)` | `strengthKey(r)` |
| Pairwise comparison | `compare_strength(a, b)` | `compareStrength(a, b)` |
| Errors | `BreadthValidationError` | `BreadthValidationError` |

## Edge cases & limitations

- **`0 / 90` is `0.0`, not a state.** Only a zero denominator is undefined.
- **`no_movers` ≠ `no_declines`.** A frozen market and a market with no
  decliners are opposite readings; they get different states and different
  `direction` values.
- **A ratio of `1.0` is `balanced`**, not "no signal".
- **Coverage is not quality.** `coverage_ratio == 1.0` with a stale
  `universe_revision` is still wrong — the policy fields travel with the result
  so the reader can check.
- **The A/D Ratio is scale-free but not universe-free.** `2.0` on the NYSE and
  `2.0` on a 50-name sector index are not comparable observations.
- **This is not a signal.** Breadth describes participation, not future
  direction.

## Testing

**Python** (59 tests)

```bash
cd python && pip install -e ".[dev]" && pytest
```

**TypeScript** (27 tests, zero runtime dependencies)

```bash
cd typescript && npm install && npm test && npm run build
```

Both suites walk the same `ad_ratio_fixtures.json` — 12 valid, 12 invalid, and
10 point-in-time cases — and assert every expected field. That shared file is
what makes the cross-language parity claim checkable rather than aspirational.

## Related algorithms

- `D04-F01-A01` — [Net Advances](https://github.com/IslamBaraka90/Fintech-Net-Advances-Market-Breadth-algorithm) (the subtraction to this division)
- `D04-F01-A03` — [Cumulative A/D Line](https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/cumulative-advance-decline-line/) ·
  `A04` — [Normalized A/D Line](https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/normalized-advance-decline-line/) ·
  `A05` — [Absolute Breadth Index](https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/absolute-breadth-index/)
- `D04-F02-A01` — [Traditional McClellan Oscillator](https://thefintechbuilder.com/market-breadth-and-internals/mcclellan-family/traditional-mcclellan-oscillator/)
- `D07-F01-A02` — [EMA](https://github.com/IslamBaraka90/Fintech-EMA-Exponential-Moving-Average-algorithm) (the smoothing the McClellan family uses)

Full index: **[Awesome FinTech Algorithms](https://github.com/IslamBaraka90/Fintech-Algorithms-Awesome)**.

## License

[MIT](./LICENSE) © The Fintech Builder. Part of the
[100 FinTech Algorithms](https://thefintechbuilder.com) library.
