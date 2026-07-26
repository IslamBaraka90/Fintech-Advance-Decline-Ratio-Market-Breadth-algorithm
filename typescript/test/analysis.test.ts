import assert from "node:assert/strict";
import { test } from "node:test";

import { calculateAdvanceDeclineRatio } from "../src/advanceDeclineRatio.ts";
import { compareStrength, logAdRatio, percentAdvancing, strengthKey } from "../src/analysis.ts";
import { BASE } from "./fixtures.ts";

const result = (patch: Record<string, unknown> = {}) =>
  calculateAdvanceDeclineRatio({ ...BASE, ...patch } as never);

const close = (a: number, b: number) => Math.abs(a - b) < 1e-12;

test("log ratio is symmetric where the raw ratio is not", () => {
  const up = result({ advances: 60, declines: 30 }); // 2.0, +1.0 from neutral
  const down = result({ advances: 30, declines: 60 }); // 0.5, -0.5 from neutral
  assert.equal(up.advance_decline_ratio, 2);
  assert.equal(down.advance_decline_ratio, 0.5);
  // Raw ratios are asymmetric around 1.0 ...
  assert.notEqual(
    Math.abs((up.advance_decline_ratio as number) - 1),
    Math.abs((down.advance_decline_ratio as number) - 1),
  );
  // ... but their logs are exactly symmetric around 0.
  assert.ok(close(logAdRatio(up) as number, Math.log(2)));
  assert.ok(close(logAdRatio(down) as number, -Math.log(2)));
  assert.ok(close((logAdRatio(up) as number) + (logAdRatio(down) as number), 0));
});

test("balanced day has zero log ratio", () => {
  assert.ok(close(logAdRatio(result({ advances: 45, declines: 45 })) as number, 0));
});

test("percent advancing is bounded and survives zero declines", () => {
  assert.ok(close(percentAdvancing(result({ advances: 60, declines: 30 })) as number, 2 / 3));
  const noDeclines = result({ advances: 90, declines: 0 });
  assert.equal(noDeclines.advance_decline_ratio, null);
  assert.equal(percentAdvancing(noDeclines), 1);
  assert.equal(percentAdvancing(result({ advances: 0, declines: 90 })), 0);
});

test("log ratio is null where it would be infinite", () => {
  assert.equal(logAdRatio(result({ advances: 90, declines: 0 })), null);
  assert.equal(logAdRatio(result({ advances: 0, declines: 90 })), null);
});

test("helpers refuse unresolved evidence", () => {
  const provisional = result({ is_final: false });
  assert.equal(provisional.evidence_state, "incomplete");
  assert.equal(logAdRatio(provisional), null);
  assert.equal(percentAdvancing(provisional), null);
  assert.equal(strengthKey(provisional), null);
});

test("no declines ranks above every finite ratio", () => {
  const huge = result({ advances: 89, declines: 1 }); // 89.0
  const perfect = result({ advances: 90, declines: 0 });
  assert.equal(compareStrength(perfect, huge), "stronger");
  assert.equal(compareStrength(huge, perfect), "weaker");
});

test("compare strength orders finite ratios", () => {
  const strong = result({ advances: 60, declines: 30 });
  const weak = result({ advances: 30, declines: 60 });
  assert.equal(compareStrength(strong, weak), "stronger");
  assert.equal(compareStrength(weak, strong), "weaker");
  assert.equal(compareStrength(strong, result({ advances: 60, declines: 30 })), "equal");
});

test("directionless states are incomparable, not zero", () => {
  const still = result({ advances: 0, declines: 0, unchanged: 100 });
  assert.equal(still.ratio_state, "no_movers");
  assert.equal(compareStrength(still, result()), "incomparable");
  assert.equal(strengthKey(still), null);
});

test("sorting a mixed day list puts the strongest last", () => {
  const days = [
    result({ advances: 30, declines: 60 }), // 0.5
    result({ advances: 90, declines: 0 }), // no_declines -> strongest
    result({ advances: 60, declines: 30 }), // 2.0
  ];
  const ranked = [...days].sort((a, b) => {
    const ka = strengthKey(a)!;
    const kb = strengthKey(b)!;
    return ka[0] - kb[0] || ka[1] - kb[1];
  });
  assert.deepEqual(
    ranked.map((d) => d.ratio_state),
    ["finite", "finite", "no_declines"],
  );
  assert.deepEqual(
    ranked.slice(0, 2).map((d) => d.advance_decline_ratio),
    [0.5, 2],
  );
});
