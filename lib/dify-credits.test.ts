import assert from "node:assert/strict";
import { test } from "node:test";
import { estimateDifyCreditRuns } from "./dify-credits";

test("whole attempts are rounded down, including a zero balance", () => {
  for (const [remaining, perRun, runs] of [
    ["200", "1", 200], ["200", "5", 40], ["200", "10", 20],
    ["190", "5", 38], ["200", "6", 33], ["4", "5", 0], ["0", "1", 0],
  ] as const) {
    assert.deepEqual(estimateDifyCreditRuns(remaining, perRun), { status: "ready", runs, remainingError: null, perRunError: null });
  }
});

test("decimal boundaries do not lose an attempt to floating point error", () => {
  for (const [remaining, perRun, runs] of [
    ["0.3", "0.1", 3], ["0.58", "0.01", 58], ["1", "0.3", 3],
    [".3", ".1", 3], ["0.299999", "0.1", 2], ["0.300001", "0.1", 3],
    [" 12.50 ", "2.5", 5], ["0002", ".50", 4], ["1.0000000", "0.1000000", 10],
  ] as const) {
    const result = estimateDifyCreditRuns(remaining, perRun);
    assert.equal(result.status, "ready");
    assert.equal(result.runs, runs, `${remaining} / ${perRun}`);
  }
});

test("maximum input and minimum positive precision remain exact and safe", () => {
  assert.equal(estimateDifyCreditRuns("1000000", "0.000001").runs, 1_000_000_000_000);
  assert.equal(estimateDifyCreditRuns("0.000001", "1000000").runs, 0);
  assert.equal(estimateDifyCreditRuns("1000000", "1000000").runs, 1);
  assert.equal(estimateDifyCreditRuns("1000000.000001", "1").remainingError, "range");
  assert.equal(estimateDifyCreditRuns("1", "1000001").perRunError, "range");
});

test("empty fields have no computed result and do not masquerade as zero", () => {
  for (const [remaining, perRun] of [["", ""], [" ", "1"], ["200", ""], ["0", " "]]) {
    const result = estimateDifyCreditRuns(remaining, perRun);
    assert.equal(result.status, "incomplete");
    assert.equal(result.runs, null);
  }
});

test("zero consumption cannot produce unlimited or free executions", () => {
  for (const zero of ["0", "0.0", ".000000", "000"]) {
    const result = estimateDifyCreditRuns("200", zero);
    assert.equal(result.status, "invalid");
    assert.equal(result.perRunError, "zero");
    assert.equal(result.runs, null);
  }
});

test("negative, nonfinite, nondecimal, and oversized inputs are rejected in either field", () => {
  for (const invalid of ["-1", "-0", "NaN", "Infinity", "-Infinity", "1e3", "1e-9", "1,000", "1/2", "0x10", ".", "+1", "１２", "9".repeat(1000)]) {
    const left = estimateDifyCreditRuns(invalid, "1");
    const right = estimateDifyCreditRuns("200", invalid);
    assert.equal(left.status, "invalid", invalid);
    assert.equal(right.status, "invalid", invalid);
    assert.equal(left.runs, null);
    assert.equal(right.runs, null);
  }
});

test("unsupported precision is reported without silently rounding it", () => {
  assert.equal(estimateDifyCreditRuns("0.0000001", "1").remainingError, "precision");
  assert.equal(estimateDifyCreditRuns("200", "0.0000001").perRunError, "precision");
  assert.equal(estimateDifyCreditRuns("1.1234567", "1").runs, null);
  assert.equal(estimateDifyCreditRuns("-1", "").status, "invalid");
});
