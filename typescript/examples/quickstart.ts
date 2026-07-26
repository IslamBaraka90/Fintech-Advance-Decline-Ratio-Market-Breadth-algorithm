/**
 * Quickstart: the A/D Ratio, its two states, and why logs beat raw ratios.
 *
 * Run:  node --experimental-strip-types examples/quickstart.ts
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  calculateAdvanceDeclineRatio,
  evaluateAdvanceDeclineRatioAsOf,
} from "../src/advanceDeclineRatio.ts";
import { compareStrength, logAdRatio, percentAdvancing } from "../src/analysis.ts";

const FIXTURE = JSON.parse(
  readFileSync(fileURLToPath(new URL("../test/fixtures/ad_ratio_fixtures.json", import.meta.url)), "utf8"),
);
const { base_snapshot: base, named_snapshots: named, query } = FIXTURE;
const calc = (patch: Record<string, unknown> = {}) =>
  calculateAdvanceDeclineRatio({ ...base, ...patch } as never);

// 1) A clean snapshot publishes its ratio.
const clean = calc();
console.log(`clean:       evidence=${clean.evidence_state} ratio_state=${clean.ratio_state} ratio=${clean.advance_decline_ratio}`);

// 2) The same finite ratio, but 20 halted issues -> observable, NOT publishable.
const poor = calc({ advances: 50, declines: 25, unchanged: 5, halted: 20 });
console.log(`low cover:   evidence=${poor.evidence_state} ratio_state=${poor.ratio_state} ratio=${poor.advance_decline_ratio} (observed ${poor.observed_partition_ratio})`);

// 3) Nothing declined: a state, not infinity.
const nd = calc({ advances: 90, declines: 0 });
console.log(`no declines: evidence=${nd.evidence_state} ratio_state=${nd.ratio_state} ratio=${nd.advance_decline_ratio}  (percent advancing still ${percentAdvancing(nd)})`);

// 4) Ratios are asymmetric; logs are not.
const up = calc({ advances: 60, declines: 30 });
const down = calc({ advances: 30, declines: 60 });
console.log(`\nmirror days: ${up.advance_decline_ratio} vs ${down.advance_decline_ratio}  -> raw distance from 1.0 differs (${Math.abs((up.advance_decline_ratio as number) - 1)} vs ${Math.abs((down.advance_decline_ratio as number) - 1)})`);
console.log(`             log ${(logAdRatio(up) as number).toFixed(6)} vs ${(logAdRatio(down) as number).toFixed(6)}  -> symmetric`);

// 5) Point-in-time: a correction must not rewrite an earlier decision.
const snapshots = [base, { ...base, ...named.correction }];
console.log();
for (const decision of ["2026-01-05T21:30:00Z", "2026-01-06T10:00:00Z"]) {
  const r = evaluateAdvanceDeclineRatioAsOf(snapshots, { ...query, decision_as_of: decision });
  console.log(`as of ${decision}: rev ${r.selected_revision} -> ratio ${(r.advance_decline_ratio as number).toFixed(6)}`);
}

// 6) Ranking treats "nothing declined" as the strongest reading, not missing data.
console.log(`\nno_declines vs 2.0 -> ${compareStrength(nd, clean)}`);
