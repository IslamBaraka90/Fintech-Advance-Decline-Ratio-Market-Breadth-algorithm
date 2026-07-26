/**
 * Comparison helpers for a fundamentally asymmetric metric.
 *
 * The A/D ratio is a **ratio**, and ratios are not symmetric around their
 * neutral point. "Twice as many advances as declines" is `2.0`; the mirror-image
 * day is `0.5`. Those are equally strong readings in opposite directions, but
 * `2.0` sits 1.0 above neutral while `0.5` sits only 0.5 below it. Averaging or
 * ranking raw ratios therefore over-weights up days and compresses down days.
 *
 * - `logAdRatio` — `ln(advances / declines)`, which *is* symmetric.
 * - `percentAdvancing` — bounded `[0, 1]`, and still defined when nothing declined.
 * - `compareStrength` / `strengthKey` — ordering that treats `no_declines` as
 *   *stronger* than any finite ratio rather than as missing data.
 *
 * Every function returns `null` when the evidence does not support a published
 * number — the same refusal-to-guess rule as the calculator itself.
 */

import type { BreadthResult } from "./advanceDeclineRatio.ts";

export type Strength = "stronger" | "weaker" | "equal" | "incomparable";

function publishable(result: BreadthResult): boolean {
  return result.evidence_state === "resolved";
}

/** `ln(advances / declines)` — the symmetric form. `null` where undefined. */
export function logAdRatio(result: BreadthResult): number | null {
  if (!publishable(result) || result.ratio_state !== "finite") return null;
  const { advances, declines } = result;
  if (!advances || !declines) return null; // 0 advances would give -inf
  return Math.log(advances / declines);
}

/** `advances / (advances + declines)` in `[0, 1]`. Stays defined at zero declines. */
export function percentAdvancing(result: BreadthResult): number | null {
  if (!publishable(result)) return null;
  const movers = result.mover_count;
  const advances = result.advances;
  if (!movers || advances === null || advances === undefined) return null;
  return advances / movers;
}

/**
 * Sortable key ordering results from weakest to strongest breadth. `no_declines`
 * ranks above every finite ratio, which naive numeric sorting on a `null` ratio
 * would get wrong. `null` for results that cannot be ranked.
 */
export function strengthKey(result: BreadthResult): [number, number] | null {
  if (!publishable(result)) return null;
  if (result.ratio_state === "no_declines") return [1, Infinity];
  if (result.ratio_state === "finite") {
    const ratio = result.advance_decline_ratio;
    return ratio === null || ratio === undefined ? null : [0, ratio];
  }
  return null; // no_movers / empty_universe carry no direction
}

/** Compare two results by breadth strength. */
export function compareStrength(left: BreadthResult, right: BreadthResult): Strength {
  const a = strengthKey(left);
  const b = strengthKey(right);
  if (a === null || b === null) return "incomparable";
  if (a[0] === b[0] && a[1] === b[1]) return "equal";
  if (a[0] !== b[0]) return a[0] > b[0] ? "stronger" : "weaker";
  return a[1] > b[1] ? "stronger" : "weaker";
}
