/**
 * Shared fixture loading — the same dataset the Python suite drives off, which
 * is what makes the cross-language parity claim real rather than aspirational.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { BreadthQuery, BreadthSnapshot } from "../src/advanceDeclineRatio.ts";

const FIXTURE = JSON.parse(
  readFileSync(fileURLToPath(new URL("./fixtures/ad_ratio_fixtures.json", import.meta.url)), "utf8"),
);

export const BASE: BreadthSnapshot = FIXTURE.base_snapshot;
export const NAMED: Record<string, Partial<BreadthSnapshot>> = FIXTURE.named_snapshots;
export const QUERY: BreadthQuery = FIXTURE.query;

export const VALID_CASES: Array<{
  name: string;
  patch?: Record<string, unknown>;
  expected: Record<string, unknown>;
}> = FIXTURE.valid_cases;

export const INVALID_CASES: Array<{
  name: string;
  patch?: Record<string, unknown>;
  remove?: string;
}> = FIXTURE.invalid_cases;

export const VERSION_CASES: Array<{
  name: string;
  decision_as_of?: string;
  snapshots: string[];
  expected: Record<string, unknown>;
}> = FIXTURE.version_cases;

/** Apply a case's `patch` / `remove` to the base snapshot. */
export function snapshotFor(item: { patch?: Record<string, unknown>; remove?: string }): BreadthSnapshot {
  const snapshot = { ...BASE, ...(item.patch ?? {}) } as Record<string, unknown>;
  if (item.remove) delete snapshot[item.remove];
  return snapshot as unknown as BreadthSnapshot;
}

/** Named snapshots are patches onto base, not standalone records. */
export function namedSnapshot(name: string): BreadthSnapshot {
  return name === "base"
    ? ({ ...BASE } as BreadthSnapshot)
    : ({ ...BASE, ...NAMED[name] } as BreadthSnapshot);
}
