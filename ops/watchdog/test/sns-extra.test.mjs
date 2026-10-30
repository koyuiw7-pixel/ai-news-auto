import assert from "node:assert/strict";
import { test } from "node:test";
import { snsExtra, snsSlots, snsAccepted, SNS_EXTRA_PREFIX, SNS_EXTRA_LAST_ATTEMPT } from "../src/sns-extra.js";

const at = (s) => new Date(s);
const DIGEST = "digest-20261030"; // morning_digest.py の実際の %Y%m%d 履歴キー
const DIGEST_KV = `${SNS_EXTRA_PREFIX}digest-2026-10-30`;
const T0 = at("2026-10-29T21:33:00Z"); // 金曜 06:33 JST
const accepted = () => ({ id: "thread-id", channels: { twitter: "x-id" } });

function harness() {
  const store = new Map();
  const calls = { reads: [], writes: [], dispatches: [] };
  const world = { state: { posted: {} }, runs: [] };
  const env = {
    SNS_EXTRA_ENABLED: "1",
    FAST: {
      async get(key) {
        if (world.kvReadError) throw new Error("private diagnostic");
        return store.has(key) ? JSON.parse(store.get(key)) : null;
      },
      async put(key, value, options) {
        if (world.kvWriteError) throw new Error("private diagnostic");
        calls.writes.push({ key, options });
        store.set(key, value);
      },
    },
  };
  const gh = async (path, init = {}) => {
    calls.reads.push(path);
    if (path.startsWith("/contents/")) {
      if (world.stateError) throw new Error("private diagnostic");
      return world.stateRaw ?? JSON.stringify(world.state);
    }
    if (path.includes("/runs?")) {
      if (world.runsError) throw new Error("private diagnostic");
      return world.runsResponse ?? { workflow_runs: world.runs };
    }
    if (path.endsWith("/dispatches")) {
      // POST が受理されても応答だけが失われる状況を再現。
      calls.dispatches.push(JSON.parse(init.body));
      if (world.dispatchError) throw new Error("private diagnostic");
      return null;
    }
    throw new Error(`unexpected request: ${path}`);
  };
  const run = (now = T0, overrides = {}) => snsExtra({ ...env, ...overrides }, now, { gh });
  return { env, world, store, calls, run };
}

test("JST の日付・当日窓・火金だけの問いかけを守る", () => {
  assert.deepEqual(snsSlots(at("2026-10-29T21:29:59Z")), []);
  assert.deepEqual(snsSlots(at("2026-10-29T21:30:00Z")), [{ kind: "digest", date: "2026-10-30" }]);
  assert.deepEqual(snsSlots(at("2026-10-30T01:59:59Z")).map((s) => s.kind), ["digest"]);
  assert.deepEqual(snsSlots(at("2026-10-30T02:00:00Z")).map((s) => s.kind), ["poll", "digest"]);
  assert.deepEqual(snsSlots(at("2026-10-30T09:00:00Z")).map((s) => s.kind), ["poll"]);
  assert.deepEqual(snsSlots(at("2026-10-30T11:00:00Z")), []);
  assert.deepEqual(snsSlots(at("2026-10-31T03:00:00Z")).map((s) => s.kind), ["digest"]);
  assert.deepEqual(snsSlots(at("2026-11-03T03:00:00Z")).map((s) => s.kind), ["poll", "digest"]);
  assert.deepEqual(snsSlots(new Date("invalid")), []);
});

test("明示有効化前と時間外は API・KV を触らない", async () => {
  for (const enabled of [undefined, "0", "true"]) {
    const h = harness();
    assert.equal((await h.run(T0, { SNS_EXTRA_ENABLED: enabled })).skip, "disabled");
    assert.deepEqual(h.calls, { reads: [], writes: [], dispatches: [] });
  }
  const h = harness();
  assert.equal((await h.run(at("2026-10-30T11:00:00Z"))).skip, "outside-window");
  assert.equal(h.calls.reads.length, 0);
});

test("既存の両媒体 ID と明示された対象媒体だけを受理済みとする", () => {
  assert.equal(snsAccepted(accepted()), true);
  assert.equal(snsAccepted({ id: "t", channels: {} }), false);
  assert.equal(snsAccepted({ id: "t", expectedChannels: ["threads"] }), true);
  assert.equal(snsAccepted({ id: "t", expectedChannels: [] }), false);
  assert.equal(snsAccepted({ ...accepted(), expectedChannels: null }), false);
  assert.equal(snsAccepted({ id: "t", expectedChannels: ["threads", "facebook"] }), false);
  assert.equal(snsAccepted({ ...accepted(), delivery: null }), false);
  assert.equal(snsAccepted({ ...accepted(), delivery: {} }), false);
  for (const status of ["accepted", "scheduled", "sending", "sent"]) {
    assert.equal(snsAccepted({ ...accepted(), delivery: { threads: { status: "sent" }, twitter: { status } } }), true);
  }
  for (const status of ["unknown", "error", "draft", "needs_approval", "rejected", "unexpected"]) {
    assert.equal(snsAccepted({ ...accepted(), delivery: { twitter: { status } } }), false, status);
  }
});

test("両媒体受理済みは実行履歴を取得する前に終了する", async () => {
  const h = harness();
  h.world.state.posted[DIGEST] = accepted();
  const log = await h.run();
  assert.equal(log.decisions[0].skip, "accepted");
  assert.equal(h.calls.reads.length, 1);
  assert.equal(h.calls.dispatches.length, 0);
});

test("片側欠落・受理不明は成功扱いせず、固定日付で一度だけ起動する", async () => {
  for (const entry of [{ id: "t", channels: {} }, { ...accepted(), delivery: { twitter: { status: "unknown" } } }]) {
    const h = harness();
    h.world.state.posted[DIGEST] = entry;
    const log = await h.run();
    assert.deepEqual(log.dispatched, { kind: "digest", date: "2026-10-30", test: "false" });
    assert.deepEqual(h.calls.dispatches[0], { ref: "main", inputs: log.dispatched });
    assert.equal(h.calls.writes[0].key, DIGEST_KV);
    assert.equal(h.calls.writes[0].options.expirationTtl, 7 * 86400);
    assert.equal((await h.run(new Date(T0.getTime() + 10 * 60000))).decisions[0].skip, "cooldown");
    assert.equal(h.calls.dispatches.length, 1);
  }
});

test("extraPending journal は投稿完了と見なさず照合ジョブへ渡す", async () => {
  const h = harness();
  h.world.state.extraPending = { [DIGEST]: { expectedChannels: ["threads", "twitter"], delivery: { threads: { status: "unknown" } } } };
  assert.equal((await h.run()).dispatched.kind, "digest");
});

test("起動中・待機中なら dispatch と KV 更新をしない", async () => {
  for (const status of ["queued", "in_progress", "waiting", "requested", "pending", "unexpected"]) {
    const h = harness();
    h.world.runs = [{ status }];
    assert.equal((await h.run()).skip, "workflow-active", status);
    assert.equal(h.calls.dispatches.length, 0);
    assert.equal(h.calls.writes.length, 0);
  }
});

test("成功ジョブがあっても媒体不足なら再試行し、失敗ジョブでも二重起動しない", async () => {
  const h = harness();
  h.world.runs = [{ status: "completed", conclusion: "success" }];
  assert.ok((await h.run()).dispatched);
  h.world.runs = [{ status: "completed", conclusion: "failure" }];
  assert.equal((await h.run(new Date(T0.getTime() + 10 * 60000))).decisions[0].skip, "cooldown");
});

test("最短20分、同じ日・kindは最大3回で止まり、翌日は新しいキー", async () => {
  const h = harness();
  for (const offset of [0, 20, 40]) assert.ok((await h.run(new Date(T0.getTime() + offset * 60000))).dispatched);
  assert.equal((await h.run(new Date(T0.getTime() + 60 * 60000))).decisions[0].skip, "daily-limit");
  assert.equal(h.calls.dispatches.length, 3);
  assert.ok((await h.run(new Date(T0.getTime() + 86400000))).dispatched);
  assert.equal(h.calls.dispatches[3].inputs.date, "2026-10-31");
});

test("POST 応答不明は回数と間隔を残し、エラー文字列をログに出さない", async () => {
  const h = harness();
  h.world.dispatchError = true;
  assert.equal((await h.run()).error, "dispatch-outcome-unknown");
  h.world.dispatchError = false;
  assert.equal((await h.run(new Date(T0.getTime() + 10 * 60000))).decisions[0].skip, "cooldown");
  const next = await h.run(new Date(T0.getTime() + 20 * 60000));
  assert.equal(next.attempts, 2);
  assert.doesNotMatch(JSON.stringify(next), /private diagnostic/);
});

test("DRY は不足確認まで行い、POST と KV 書き込みはしない", async () => {
  const h = harness();
  const log = await h.run(T0, { SNS_EXTRA_DRY_RUN: "1" });
  assert.equal(log.wouldDispatch.kind, "digest");
  assert.equal(h.calls.dispatches.length, 0);
  assert.equal(h.calls.writes.length, 0);
});

test("読み取り失敗・不正な記録は未投稿と解釈せず停止する", async () => {
  for (const change of [
    { stateError: true }, { stateRaw: "bad json" }, { stateRaw: "{}" },
    { stateRaw: '{"posted":[],"extraPending":{}}' },
    { stateRaw: '{"posted":{},"extraPending":[]}' },
    { runsError: true }, { runsResponse: {} }, { runsResponse: { workflow_runs: [null] } },
    { kvReadError: true }, { kvWriteError: true },
  ]) {
    const h = harness();
    Object.assign(h.world, change);
    const log = await h.run();
    assert.ok(log.error || log.decisions.some((d) => d.error), JSON.stringify(change));
    assert.equal(h.calls.dispatches.length, 0);
  }
  const h = harness();
  h.store.set(DIGEST_KV, JSON.stringify({ attempts: "bad" }));
  assert.equal((await h.run()).decisions[0].error, "dispatch-state-unavailable");
  assert.equal(h.calls.dispatches.length, 0);
});

test("金曜昼は1枠ずつ起動し、kind が変わっても20分間隔を空ける", async () => {
  const h = harness();
  const noon = at("2026-10-30T03:03:00Z");
  assert.equal((await h.run(noon)).dispatched.kind, "poll");
  assert.equal(h.calls.dispatches.length, 1);
  h.world.state.posted["poll-20261030"] = accepted();
  assert.equal((await h.run(new Date(noon.getTime() + 10 * 60000))).skip, "global-cooldown");
  assert.equal((await h.run(new Date(noon.getTime() + 20 * 60000))).dispatched.kind, "digest");
  assert.equal(h.calls.dispatches.length, 2);
  assert.equal(h.calls.writes.every((w) => w.key.startsWith(SNS_EXTRA_PREFIX)), true);
  assert.ok(h.store.has(SNS_EXTRA_LAST_ATTEMPT));
});

test("別 kind の実際の compact 履歴・直近受付・近日予約を見て20分の連投を避ける", async () => {
  for (const [field, stamp] of [["postedAt", "2026-10-30T03:00:00Z"], ["dueAt", "2026-10-30T03:15:00Z"]]) {
    const h = harness();
    h.world.state.posted["poll-20261030"] = { ...accepted(), [field]: stamp };
    const log = await h.run(at("2026-10-30T03:03:00Z"));
    assert.equal(log.decisions.find((d) => d.kind === "poll").skip, "accepted");
    assert.equal(log.decisions.find((d) => d.kind === "digest").skip, "other-kind-spacing");
    assert.equal(h.calls.dispatches.length, 0);
    assert.equal((await h.run(at("2026-10-30T03:35:00Z"))).dispatched.kind, "digest");
  }
});

test("kind 横断 KV が不明でも dispatch せず、未来の予約時刻は間隔を縮めない", async () => {
  const h = harness();
  h.store.set(SNS_EXTRA_LAST_ATTEMPT, JSON.stringify({ version: 1, attempts: "bad" }));
  assert.equal((await h.run()).error, "global-dispatch-state-unavailable");
  assert.equal(h.calls.dispatches.length, 0);
  h.store.set(SNS_EXTRA_LAST_ATTEMPT, JSON.stringify({ version: 1, attempts: 1, lastAttemptAt: new Date(T0.getTime() + 60000).toISOString() }));
  assert.equal((await h.run()).skip, "global-cooldown");
  assert.equal(h.calls.dispatches.length, 0);
});
