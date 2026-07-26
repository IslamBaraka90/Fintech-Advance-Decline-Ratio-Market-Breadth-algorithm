import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BreadthValidationError,
  calculateAdvanceDeclineRatio,
  evaluateAdvanceDeclineRatioAsOf,
  type BreadthQuery,
} from "../src/advanceDeclineRatio.ts";
import {
  BASE,
  INVALID_CASES,
  QUERY,
  VALID_CASES,
  VERSION_CASES,
  namedSnapshot,
  snapshotFor,
} from "./fixtures.ts";

const result = (patch: Record<string, unknown> = {}) =>
  calculateAdvanceDeclineRatio({ ...BASE, ...patch } as never);

/**
 * Compare one expected fixture field. Some expectations (notably `reasons`) are
 * arrays, so a strict `assert.equal` would compare object identity and always
 * fail — mirror Python's `==`, which compares lists by value.
 */
function assertField(actual: unknown, expected: unknown, label: string): void {
  if (Array.isArray(expected)) assert.deepEqual(actual, expected, label);
  else assert.equal(actual, expected, label);
}

// --- the 34 named fixture cases ------------------------------------------- //
test("valid cases", () => {
  for (const item of VALID_CASES) {
    const r = calculateAdvanceDeclineRatio(snapshotFor(item)) as unknown as Record<string, unknown>;
    for (const [key, value] of Object.entries(item.expected)) {
      assertField(r[key], value, `${item.name}.${key}`);
    }
  }
});

test("invalid cases raise", () => {
  for (const item of INVALID_CASES) {
    assert.throws(
      () => calculateAdvanceDeclineRatio(snapshotFor(item)),
      BreadthValidationError,
      item.name,
    );
  }
});

test("version cases", () => {
  for (const item of VERSION_CASES) {
    const snapshots = item.snapshots.map(namedSnapshot);
    const query = { ...QUERY, decision_as_of: item.decision_as_of ?? QUERY.decision_as_of };
    const r = evaluateAdvanceDeclineRatioAsOf(snapshots, query) as unknown as Record<string, unknown>;
    for (const [key, value] of Object.entries(item.expected)) {
      assertField(r[key], value, `${item.name}.${key}`);
    }
  }
});

// --- the two design decisions this algorithm turns on --------------------- //
test("zero declines is a state, not infinity", () => {
  const r = result({ advances: 90, declines: 0 });
  assert.equal(r.ratio_state, "no_declines");
  assert.equal(r.advance_decline_ratio, null);
  assert.equal(r.observed_partition_ratio, null);
  assert.equal(r.direction, "advances_only");
  assert.equal(r.evidence_state, "resolved");
});

test("evidence state and ratio state are independent", () => {
  const poor = result({ advances: 50, declines: 25, unchanged: 5, halted: 20 });
  assert.equal(poor.ratio_state, "finite");
  assert.equal(poor.evidence_state, "incomplete");
  assert.equal(poor.advance_decline_ratio, null);
  assert.equal(poor.observed_partition_ratio, 2);
  assert.ok(poor.reasons.includes("coverage_is_incomplete"));
});

test("observed ratio is always reported even when unpublishable", () => {
  const r = result({ is_final: false });
  assert.equal(r.is_provisional, true);
  assert.equal(r.evidence_state, "incomplete");
  assert.equal(r.advance_decline_ratio, null);
  assert.equal(r.observed_partition_ratio, 2);
  assert.equal(r.observed_partition_direction, "advances_dominant");
  assert.ok(r.reasons.includes("snapshot_is_provisional"));
});

test("clean snapshot publishes the ratio", () => {
  const r = result();
  assert.equal(r.evidence_state, "resolved");
  assert.equal(r.advance_decline_ratio, 2);
  assert.equal(r.observed_partition_ratio, 2);
  assert.equal(r.direction, "advances_dominant");
  assert.deepEqual(r.reasons, []);
});

test("zero advances is finite, not a special state", () => {
  const r = result({ advances: 0, declines: 90 });
  assert.equal(r.ratio_state, "finite");
  assert.equal(r.advance_decline_ratio, 0);
  assert.equal(r.direction, "declines_dominant");
});

// --- partition, coverage, raise-vs-status --------------------------------- //
test("partition mismatch raises rather than returning a status", () => {
  assert.throws(() => result({ universe_size: 99 }), BreadthValidationError);
});

test("coverage ratio is classified over universe", () => {
  assert.equal(result().coverage_ratio, 1);
  const partial = result({ unchanged: 0, halted: 10 });
  assert.equal(partial.classified_count, 90);
  assert.equal(partial.coverage_ratio, 0.9);
  assert.equal(partial.excluded_count, 10);
});

test("empty universe and no movers are distinct", () => {
  const empty = result({ advances: 0, declines: 0, unchanged: 0, universe_size: 0 });
  assert.equal(empty.ratio_state, "empty_universe");
  assert.equal(empty.direction, "no_universe");
  assert.equal(empty.coverage_ratio, null);

  const still = result({ advances: 0, declines: 0, unchanged: 100 });
  assert.equal(still.ratio_state, "no_movers");
  assert.equal(still.direction, "no_movers");
  assert.equal(still.coverage_ratio, 1);
});

// --- point-in-time selection ---------------------------------------------- //
test("a later correction cannot change an earlier decision", () => {
  const snapshots = [namedSnapshot("base"), namedSnapshot("correction")];
  const before = evaluateAdvanceDeclineRatioAsOf(snapshots, {
    ...QUERY,
    decision_as_of: "2026-01-05T21:30:00Z",
  });
  const after = evaluateAdvanceDeclineRatioAsOf(snapshots, {
    ...QUERY,
    decision_as_of: "2026-01-06T10:00:00Z",
  });
  assert.equal(before.selected_revision, 1);
  assert.equal(before.advance_decline_ratio, 2);
  assert.equal(after.selected_revision, 2);
  assert.equal(after.advance_decline_ratio, 58 / 32);
});

test("a competing highest revision is ambiguous, not a guess", () => {
  const r = evaluateAdvanceDeclineRatioAsOf(
    [namedSnapshot("base"), namedSnapshot("correction"), namedSnapshot("conflict")],
    QUERY,
  );
  assert.equal(r.evidence_state, "ambiguous");
  assert.equal(r.advance_decline_ratio, null);
  assert.deepEqual(r.reasons, ["conflicting_highest_revision"]);
});

test("snapshots for another universe or policy are not selected", () => {
  for (const name of ["other_universe", "different_policy"]) {
    const r = evaluateAdvanceDeclineRatioAsOf([namedSnapshot(name)], QUERY);
    assert.equal(r.evidence_state, "unsupported", name);
  }
});

test("nothing available yet is unsupported", () => {
  const r = evaluateAdvanceDeclineRatioAsOf([namedSnapshot("base")], {
    ...QUERY,
    decision_as_of: "2026-01-05T21:04:59Z",
  });
  assert.equal(r.evidence_state, "unsupported");
  assert.deepEqual(r.reasons, ["no_snapshot_available_as_of_query"]);
});

test("a future malformed snapshot does not leak into an earlier query", () => {
  const r = evaluateAdvanceDeclineRatioAsOf(
    [namedSnapshot("base"), namedSnapshot("future_malformed")],
    { ...QUERY, decision_as_of: "2026-01-05T21:30:00Z" },
  );
  assert.equal(r.evidence_state, "resolved");
  assert.equal(r.selected_revision, 1);
});

test("query requires every policy field", () => {
  for (const field of Object.keys(QUERY)) {
    if (field === "decision_as_of") continue;
    const broken = { ...QUERY, [field]: "" } as unknown as BreadthQuery;
    assert.throws(
      () => evaluateAdvanceDeclineRatioAsOf([namedSnapshot("base")], broken),
      BreadthValidationError,
      field,
    );
  }
});

test("result reports the selected record for audit", () => {
  const r = evaluateAdvanceDeclineRatioAsOf(
    [namedSnapshot("base"), namedSnapshot("correction")],
    QUERY,
  );
  assert.equal(r.selected_record_id, "SYNTH-2026-01-05-R2");
  assert.equal(r.selected_revision, 2);
  assert.equal(r.metric, "advancing_issues_divided_by_declining_issues");
});
