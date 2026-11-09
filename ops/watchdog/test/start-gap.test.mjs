import { test } from "node:test";
import assert from "node:assert/strict";
import { isDaytimeJst, startGapMin } from "../src/start-gap.js";

const env = { START_GAP_MIN: "18", DAY_START_GAP_MIN: "14" };

test("日本時間 6:00〜24:00 は昼の間隔", () => {
  assert.equal(isDaytimeJst(new Date("2026-11-09T21:00:00Z")), true); // 6:00 JST
  assert.equal(isDaytimeJst(new Date("2026-11-09T14:58:00Z")), true); // 23:58 JST
  assert.equal(isDaytimeJst(new Date("2026-11-09T15:00:00Z")), false); // 0:00 JST
  assert.equal(isDaytimeJst(new Date("2026-11-09T20:58:00Z")), false); // 5:58 JST
  assert.equal(startGapMin(env, new Date("2026-11-09T06:00:00Z")), 14);
  assert.equal(startGapMin(env, new Date("2026-11-09T18:00:00Z")), 18);
  assert.equal(startGapMin({ START_GAP_MIN: "18" }, new Date("2026-11-09T06:00:00Z")), 18);
});
