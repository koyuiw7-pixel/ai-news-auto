// 地震・津波レーンのテスト（node --test test/）。電文は気象庁の公式サンプル（jmaxml_20260917_Samples）と、実際の震度3の電文
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { parseQuake, quakeLane, triggers } from "../src/quake.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..", "..");
const RULES = JSON.parse(readFileSync(join(ROOT, "scripts", "fast_lane_rules.json"), "utf-8"));
const Q = RULES.quake;
const jma = (name) => readFileSync(join(HERE, "fixtures", "jma", name), "utf-8");
const FIX = {
  s51: "sample_VXSE51_6plus.xml",
  t41: "sample_VTSE41_major.xml",
  s53: "sample_VXSE53_7.xml",
  lifted: "sample_VTSE41_lifted.xml",
  int3: "real_VXSE53_int3.xml",
};

function py(args) {
  const r = spawnSync("python3", ["scripts/quake.py", ...args], { cwd: ROOT, encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  return r.stdout;
}

test("電文の読み取り: 震度・EventID・津波の警報の種類", () => {
  const a = parseQuake(jma(FIX.s51));
  assert.deepEqual([a.title, a.status, a.eventId, a.maxInt, a.warn], ["震度速報", "通常", "20110311144640", "6+", ""]);
  assert.equal(parseQuake(jma(FIX.t41)).warn, "大津波警報");
  assert.equal(parseQuake(jma(FIX.s53)).maxInt, "7");
  assert.equal(parseQuake(jma(FIX.lifted)).warn, "");
  assert.equal(parseQuake(jma(FIX.int3)).maxInt, "3");
});

test("対象の判定（震度5弱以上・大津波警報・津波警報）が Python（scripts/quake.py）と同じ", () => {
  const expect = { s51: true, t41: true, s53: true, lifted: false, int3: false };
  for (const [k, f] of Object.entries(FIX)) {
    const mine = triggers(parseQuake(jma(f)), Q);
    assert.equal(mine, expect[k], f);
    const theirs = JSON.parse(py(["--render", join(HERE, "fixtures", "jma", f), "--json"]))._triggers;
    assert.equal(theirs, mine, `${f}（Python）`);
  }
  // 訓練の電文は使わない
  assert.equal(triggers({ ...parseQuake(jma(FIX.s51)), status: "訓練" }, Q), false);
});

test("記事の書式: LLM なし・数字は電文どおり・気象庁へのリンク・写真なし・安全の通知", () => {
  const files = [FIX.s51, FIX.t41, FIX.s53].map((f) => join(HERE, "fixtures", "jma", f));
  const a = JSON.parse(py(["--render", ...files, "--json", "--now", "2011-03-11T15:05:00+09:00"]));
  assert.equal(a.slug, "quake-20110311144640");
  assert.match(a.title, /^【大津波警報】.*最大震度7/);
  assert.match(a.body, /\| 発生時刻 \| 2011年3月11日 14時46分ごろ \|/);
  assert.match(a.body, /\| 深さ \| 約10km \|/);
  assert.match(a.body, /マグニチュード8を超える巨大地震/);
  assert.match(a.body, /\*\*震度7\*\*: 宮城県北部/);
  assert.match(a.body, /\*\*大津波警報\*\*: 岩手県/);
  assert.match(a.body, /最新情報は気象庁で確認してください/);
  assert.match(a.body, /https:\/\/www\.jma\.go\.jp\/bosai\/map\.html#contents=tsunami/);
  // 被害の記述はしない（「含みません」というお断りの文だけ）
  assert.doesNotMatch(a.body.replace("被害の状況や今後の見通しは含みません。", ""), /被害|死者|けが/);
  assert.equal(a.model, "template");
  assert.equal(a.thumbnail, "");
  assert.equal(a.noPhoto, true);
  assert.equal(a.breaking, true);
  assert.equal(a.safetyAlert, true);
  assert.equal(a.genreSlug, "public");
  // 最初の電文（14:48）から書き出し＋デプロイの約3分
  assert.equal(a.speedMinutes, 20);
  // 震度3の地震は対象外で、安全の通知もしない
  const small = JSON.parse(py(["--render", join(HERE, "fixtures", "jma", FIX.int3), "--json"]));
  assert.equal(small._triggers, false);
  assert.equal(small.safetyAlert, false);
});

test("同じ地震の続報は同じ記事を書き直す（作成時刻・速さのラベルを引き継ぎ、更新履歴を足す）", () => {
  const dir = mkdtempSync(join(tmpdir(), "quake-"));
  const code = `
import sys, json
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, 'scripts')
import quake
quake.ARTICLES = Path(sys.argv[1])
d = 'ops/watchdog/test/fixtures/jma/'
b1 = [quake.parse(Path(d + 'sample_VXSE51_6plus.xml').read_bytes())]
t1 = datetime.fromisoformat('2011-03-11T14:52:00+09:00')
a1 = quake.render(quake.merge(b1), t1)
r1 = quake.write(a1, t1)[0]
b2 = b1 + [quake.parse(Path(d + f).read_bytes()) for f in ('sample_VTSE41_major.xml', 'sample_VXSE53_7.xml')]
t2 = datetime.fromisoformat('2011-03-11T15:00:00+09:00')
prev = json.loads((quake.ARTICLES / (a1['slug'] + '.json')).read_text())
r2 = quake.write(quake.render(quake.merge(b2), t2, prev), t2)[0]
r3 = quake.write(quake.render(quake.merge(b2), t2, prev), t2)[0]
out = json.loads((quake.ARTICLES / (a1['slug'] + '.json')).read_text())
print(json.dumps({'r': [r1, r2, r3], 'gen': out['generatedAt'], 'speed': out.get('speedMinutes'), 'updates': len(out.get('updates', [])), 'title': out['title'], 'files': len(list(quake.ARTICLES.glob('*.json')))}, ensure_ascii=False))
`;
  const r = spawnSync("python3", ["-c", code, dir], { cwd: ROOT, encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  const o = JSON.parse(r.stdout);
  assert.deepEqual(o.r, ["created", "updated", "same"]);
  assert.equal(o.gen, "2011-03-11T14:52:00+09:00");
  assert.equal(o.speed, 7);
  assert.equal(o.updates, 1);
  assert.match(o.title, /大津波警報/);
  assert.equal(o.files, 1);
  assert.equal(readdirSync(dir).length, 1);
});

// --------------------------------------------------------------------------- //
// 1回分の流れ（KV・feed・GitHub は偽物）
// --------------------------------------------------------------------------- //

function harness() {
  const store = new Map();
  const entries = [];
  const xml = {};
  const calls = { dispatches: [] };
  const world = { runs: [], acks: {} };
  const env = {
    REPO: "o/r", WORKFLOW: "auto_run.yml", GH_TOKEN: "x",
    FAST: {
      async get(k, type) {
        const v = store.get(k);
        return v == null ? null : type === "json" ? JSON.parse(v) : v;
      },
      async put(k, v) {
        store.set(k, v);
      },
    },
  };
  const feed = () =>
    `<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">${entries
      .map((e) => `<entry><title>${e.title}</title><id>${e.url}</id><updated>${e.at}</updated><link type="application/xml" href="${e.url}"/></entry>`)
      .join("")}</feed>`;
  const fetchImpl = async (url) => {
    if (url === Q.feed) return new Response(feed(), { status: 200, headers: { "last-modified": "x" } });
    if (url in xml) return new Response(xml[url], { status: 200 });
    return new Response("nf", { status: 404 });
  };
  const gh = async (path, init = {}) => {
    if (path.startsWith("/actions/workflows/auto_run.yml/runs")) return { workflow_runs: world.runs };
    if (path.startsWith("/contents/state/fast_lane.json")) return JSON.stringify({ items: world.acks });
    if (path.endsWith("/dispatches")) {
      calls.dispatches.push(JSON.parse(init.body));
      return null;
    }
    throw new Error(`unexpected ${path}`);
  };
  const add = (title, file, at) => {
    const url = `https://www.data.jma.go.jp/developer/xml/data/${file}`;
    entries.unshift({ title, url, at });
    xml[url] = jma(file);
    return url;
  };
  const run = (now) => quakeLane(env, new Date(now), { rules: RULES, fetch: fetchImpl, gh });
  return { run, add, calls, world, store, entries };
}

test("地震レーン: 初回は既読にするだけ → 震度6強で起動 → 同じ地震の津波警報は続報として起動 → 震度3は起動しない", async () => {
  const h = harness();
  h.add("震源・震度に関する情報", FIX.int3, "2011-03-11T05:00:00Z");
  let log = await h.run("2011-03-11T05:40:00Z");
  assert.equal(log.baseline, 1);
  assert.equal(h.calls.dispatches.length, 0);

  const u1 = h.add("震度速報", FIX.s51, "2011-03-11T05:48:00Z");
  log = await h.run("2011-03-11T05:48:30Z");
  assert.equal(h.calls.dispatches.length, 1);
  const d = h.calls.dispatches[0];
  assert.equal(d.inputs.fast_url, u1);
  const meta = JSON.parse(d.inputs.fast_meta)[0];
  assert.equal(meta.id, "quake-20110311144640");
  assert.equal(meta.eventId, "20110311144640");
  assert.equal(meta.genre, "disaster");

  // 結果が記録されたら起動し直さない
  h.world.acks["quake-20110311144640"] = { outcome: "created", finishedAt: "2011-03-11T05:52:00Z" };
  const u2 = h.add("津波警報・注意報・予報a", FIX.t41, "2011-03-11T05:49:59Z");
  log = await h.run("2011-03-11T05:50:30Z");
  assert.equal(h.calls.dispatches.length, 2);
  assert.deepEqual(JSON.parse(h.calls.dispatches[1].inputs.fast_meta)[0].urls, [u1, u2]);

  // 同じ地震の実行が待機中なら重ねない（待機中の実行が始まるときに feed を読み直す）
  h.world.runs = [{ status: "queued", display_title: `速報レーン ${u2}`, run_number: 9 }];
  h.add("震源・震度に関する情報", FIX.s53, "2011-03-11T05:54:00Z");
  log = await h.run("2011-03-11T05:54:30Z");
  assert.equal(h.calls.dispatches.length, 2);
  assert.match(log.skip, /待機中/);
  h.world.runs = [];
  log = await h.run("2011-03-11T05:56:30Z");
  assert.equal(h.calls.dispatches.length, 3);

  // 別の小さな地震（震度3）は起動しない
  h.world.acks["quake-20110311144640"] = { outcome: "updated", finishedAt: "2011-03-11T06:00:00Z" };
  const small = h.add("震源・震度に関する情報", FIX.int3, "2011-03-11T06:10:00Z");
  h.entries[0].url = `${small}?2`; // 別の電文として見せる
  log = await h.run("2011-03-11T06:10:30Z");
  assert.equal(h.calls.dispatches.length, 3);
  assert.equal(log.dispatched.length, 0);
});

test("地震レーン: 起動したのに結果が12分来なければ起動し直す（最大3回）", async () => {
  const h = harness();
  h.add("震源・震度に関する情報", FIX.int3, "2011-03-11T05:00:00Z");
  await h.run("2011-03-11T05:40:00Z");
  h.add("震度速報", FIX.s51, "2011-03-11T05:48:00Z");
  await h.run("2011-03-11T05:48:30Z");
  await h.run("2011-03-11T05:56:00Z");
  assert.equal(h.calls.dispatches.length, 1);
  await h.run("2011-03-11T06:01:00Z");
  assert.equal(h.calls.dispatches.length, 2);
  await h.run("2011-03-11T06:14:00Z");
  await h.run("2011-03-11T06:27:00Z");
  await h.run("2011-03-11T06:40:00Z");
  assert.equal(h.calls.dispatches.length, 3);
});
