// 速報レーンのテスト（node --test test/）。見出し・URL は架空のもの
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  compile, fastLane, htmlToText, itemId, metaContent, normalizeUrl, parseFeed, parseHtmlList, relevant, RUN_PREFIX,
} from "../src/fastlane.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const RULES = JSON.parse(readFileSync(join(ROOT, "scripts", "fast_lane_rules.json"), "utf-8"));
const R = compile(RULES);
const fixture = (name) => readFileSync(join(dirname(fileURLToPath(import.meta.url)), "fixtures", name), "utf-8");

function python(code, input) {
  const r = spawnSync("python3", ["-c", code], { input: JSON.stringify(input), cwd: ROOT, encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

// --------------------------------------------------------------------------- //
// 解析
// --------------------------------------------------------------------------- //

test("RSS 2.0: CDATA・実体参照・日付", () => {
  const items = parseFeed(fixture("rss2.xml"));
  assert.equal(items.length, 3);
  assert.equal(items[0].title, "Introducing Zeta-1 & Zeta-1 mini");
  assert.equal(items[0].url, "https://example-ai.test/index/introducing-zeta-1/");
  assert.equal(items[0].publishedAt, "2026-10-27T09:00:00.000Z");
  assert.equal(items[1].title, "How Acme “builds” agents");
});

test("Atom: alternate の link を使う（self・replies は使わない）", () => {
  const items = parseFeed(fixture("atom.xml"));
  assert.deepEqual(
    items.map((i) => i.url),
    ["https://dev.example.test/2026/10/zeta-api-now-available.html", "https://dev.example.test/2026/10/second.html"],
  );
  assert.equal(items[0].publishedAt, "2026-10-27T01:00:00.000Z");
});

test("RSS 1.0（RDF）: dc:date", () => {
  const items = parseFeed(fixture("rdf.xml"));
  assert.equal(items.length, 2);
  assert.equal(items[0].publishedAt, "2026-10-27T03:30:00.000Z");
  assert.equal(items[0].title, "新モデル「Zeta-2」を発表");
});

test("一覧ページの HTML: 見出し付きのリンクだけ・同じ記事は1回・カテゴリと外部リンクは除く", () => {
  const src = { url: "https://www.example-lab.test/news", link_re: "^/news/[a-z0-9][a-z0-9-]+$" };
  const items = parseHtmlList(fixture("list.html"), src);
  assert.deepEqual(
    items.map((i) => [i.url, i.title]),
    [
      ["https://www.example-lab.test/news/introducing-zeta-3", "Introducing Zeta 3"],
      ["https://www.example-lab.test/news/lab-opens-office", "Lab opens a new office in Osaka"],
    ],
  );
});

test("URL の正規化と ID が Python（feeds.item_id）と同じ", async () => {
  const urls = [
    "https://Example.test/news/a/",
    "https://example.test/news/a?utm_source=x&utm_medium=y",
    "https://example.test/news/a?id=3&utm_campaign=z",
    "https://www.example-lab.test/news/introducing-zeta-3",
  ];
  assert.equal(normalizeUrl(urls[0]), "https://example.test/news/a");
  assert.equal(normalizeUrl(urls[1]), "https://example.test/news/a");
  const mine = await Promise.all(urls.map(itemId));
  const theirs = python("import sys,json; sys.path.insert(0,'scripts'); import feeds; print(json.dumps([feeds.item_id(u) for u in json.load(sys.stdin)]))", urls);
  assert.deepEqual(mine, theirs);
});

test("記事ページの本文・og:image・公開時刻を取り出す", () => {
  const html = fixture("article.html");
  const text = htmlToText(html);
  assert.match(text, /Zeta 3 is our most capable model/);
  assert.match(text, /costs \$2 per million/);
  assert.doesNotMatch(text, /Subscribe|Cookie|function\(/);
  assert.equal(metaContent(html, "og:image"), "https://www.example-lab.test/images/zeta-3.png");
  assert.equal(metaContent(html, "article:published_time"), "2026-10-27T15:00:00Z");
});

// --------------------------------------------------------------------------- //
// 判定
// --------------------------------------------------------------------------- //

const CASES = [
  ["openai-news", "Introducing GPT-7", true],
  ["openai-news", "GPT-7.1 Mini", true],
  ["openai-news", "ChatGPT Pulse is now available in Japan", true],
  ["openai-news", "OpenAI acquires Example Robotics", true],
  ["openai-news", "GPT-7 helps Acme cut costs by 40%", false],
  ["openai-news", "How Acme is using ChatGPT to scale support", false],
  ["openai-news", "Acme cuts review time 10x with Codex", false],
  ["openai-news", "Join us for a webinar on GPT-7", false],
  ["anthropic-news", "Introducing Claude Opus 6", true],
  ["anthropic-news", "Anthropic opens a new office in Seoul", false],
  ["anthropic-news", "Example Corp scales Claude across operations", false],
  ["google-gemini-blog", "Gemini 5 Flash is rolling out to everyone", true],
  ["google-gemini-blog", "5 tips for planning trips with Gemini", false],
  ["google-deepmind-blog", "EmbeddingGemma 3: a tiny open model", true],
  ["google-deepmind-blog", "Developing Gemini 5 responsibly", false],
  ["microsoft-source", "Introducing a new employee benefit", false],
  ["microsoft-source", "Microsoft launches MAI-3 voice model", true],
  ["meta-newsroom", "Announcing the Official Selection for a film festival", false],
  ["meta-newsroom", "Introducing Muse 2: frontier models for agents", true],
  ["nvidia-blog", "GFN Thursday: 12 new games launch in the cloud", false],
  ["nvidia-blog", "NVIDIA Unveils Rubin Ultra", true],
  ["apple-newsroom-jp", "Apple、新しいiPad miniを発表", false],
  ["apple-newsroom-jp", "Apple Intelligence、日本語で提供開始", true],
  ["mistral-news", "Voxtral 3", true],
  ["mistral-news", "Mistral Advances AI for Engineering with NVIDIA", false],
  ["unknown-feed", "Introducing GPT-7", false],
];

test("判定の結果（代表例）", () => {
  for (const [source, title, expected] of CASES) {
    assert.equal(relevant(title, source, R).ok, expected, `${source}: ${title}`);
  }
});

test("判定が Python（scripts/fast_lane.py）と同じ", () => {
  const input = CASES.map(([source, title]) => ({ source, title }));
  const r = spawnSync("python3", ["scripts/fast_lane.py", "--classify"], { input: JSON.stringify(input), cwd: ROOT, encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  const theirs = JSON.parse(r.stdout);
  const mine = CASES.map(([source, title]) => relevant(title, source, R));
  assert.deepEqual(mine, theirs);
});

// --------------------------------------------------------------------------- //
// 1回分の流れ（KV・フィード・GitHub は偽物）
// --------------------------------------------------------------------------- //

const TEST_RULES = {
  ...RULES,
  sources: [
    { slug: "openai-news", name: "A", type: "rss", url: "https://feeds.test/openai.xml", entity: "openai" },
    { slug: "google-ai-blog", name: "B", type: "rss", url: "https://feeds.test/google-ai.xml", entity: "google" },
    { slug: "google-gemini-blog", name: "C", type: "rss", url: "https://feeds.test/gemini.xml", entity: "google" },
  ],
};

function rss(items) {
  const body = items
    .map((i) => `<item><title>${i.title}</title><link>${i.url}</link><pubDate>${new Date(i.at).toUTCString()}</pubDate></item>`)
    .join("");
  return `<?xml version="1.0"?><rss><channel><title>t</title>${body}</channel></rss>`;
}

function harness(rules = TEST_RULES) {
  const store = new Map();
  // 実際のフィードは空にならない（0件は解析の失敗として扱う）ので、古い記事を1件ずつ入れておく
  const old = (name) => [{ title: `Old ${name}`, url: `https://ex.test/old-${name}`, at: Date.parse("2026-10-20T00:00:00Z") }];
  const feeds = {
    "https://feeds.test/openai.xml": old("a"),
    "https://feeds.test/google-ai.xml": old("b"),
    "https://feeds.test/gemini.xml": old("c"),
  };
  const calls = { dispatches: [], requests: [] };
  const world = { runs: [], acks: {}, etag: {}, pages: {} };
  const env = {
    REPO: "o/r",
    WORKFLOW: "auto_run.yml",
    GH_TOKEN: "x",
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
  const fetchImpl = async (url, init = {}) => {
    calls.requests.push({ url, headers: init.headers || {} });
    if (world.etag[url] && init.headers?.["If-None-Match"] === world.etag[url]) return new Response(null, { status: 304 });
    if (url in world.pages) return new Response(world.pages[url], { status: 200 });
    if (!(url in feeds)) return new Response("nf", { status: 404 });
    return new Response(rss(feeds[url]), { status: 200, headers: world.etag[url] ? { etag: world.etag[url] } : {} });
  };
  const gh = async (path, init = {}) => {
    if (path.startsWith("/actions/workflows/auto_run.yml/runs")) return { workflow_runs: world.runs };
    if (path.startsWith("/contents/state/fast_lane.json")) return JSON.stringify({ items: world.acks });
    if (path.endsWith("/dispatches")) {
      const body = JSON.parse(init.body);
      calls.dispatches.push(body);
      return null;
    }
    throw new Error(`unexpected ${path}`);
  };
  const run = (now, extraEnv = {}) => fastLane({ ...env, ...extraEnv }, new Date(now), { rules, fetch: fetchImpl, gh });
  return { store, feeds, calls, world, run, state: () => JSON.parse(store.get("state")) };
}

const T0 = Date.parse("2026-10-27T10:00:00Z");
const MIN = 60000;

test("初回は既読にするだけで起動しない → 次の回の新着で起動する", async () => {
  const h = harness();
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Old post", url: "https://ex.test/old", at: T0 - 86400e3 });
  let log = await h.run(T0);
  assert.equal(log.baseline.length, 3);
  assert.equal(h.calls.dispatches.length, 0);

  h.feeds["https://feeds.test/openai.xml"].unshift(
    { title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 + MIN },
    { title: "How Acme is using ChatGPT", url: "https://ex.test/acme", at: T0 + MIN },
  );
  log = await h.run(T0 + 2 * MIN);
  assert.equal(h.calls.dispatches.length, 1);
  const inputs = h.calls.dispatches[0].inputs;
  assert.equal(inputs.mode, "web");
  assert.equal(inputs.fast_url, "https://ex.test/gpt-7");
  const meta = JSON.parse(inputs.fast_meta);
  assert.equal(meta.length, 1);
  assert.equal(meta[0].title, "Introducing GPT-7");
  assert.equal(meta[0].detectedAt, new Date(T0 + 2 * MIN).toISOString());
  assert.equal(meta[0].id, await itemId("https://ex.test/gpt-7"));
  assert.ok(log.new.some((l) => l.includes("How Acme") && !l.endsWith("対象")));

  // 同じ記事はもう新着ではない
  await h.run(T0 + 4 * MIN);
  assert.equal(h.calls.dispatches.length, 1);
});

test("起動するとき記事ページの本文・画像も渡す（パイプラインから読めないサイト向け）", async () => {
  const h = harness();
  await h.run(T0);
  h.world.pages["https://ex.test/gpt-7"] = fixture("article.html");
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  const log = await h.run(T0 + 2 * MIN);
  const meta = JSON.parse(h.calls.dispatches[0].inputs.fast_meta)[0];
  assert.match(meta.text, /most capable model/);
  assert.equal(meta.image, "https://www.example-lab.test/images/zeta-3.png");
  assert.ok(log.dispatched[0].textChars > 100);
  assert.equal(log.dispatched[0].via, "direct");
  // GitHub の入力の上限（65,535字）に十分収まる
  assert.ok(JSON.stringify(h.calls.dispatches[0].inputs).length < 40000);
});

test("記事ページが読めなくても待たずに起動する（本文は空・取得の状態をログに残す）", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-8", url: "https://ex.test/gpt-8", at: T0 });
  const log = await h.run(T0 + 2 * MIN);
  assert.equal(h.calls.dispatches.length, 1);
  assert.equal(JSON.parse(h.calls.dispatches[0].inputs.fast_meta)[0].text, "");
  assert.deepEqual(log.dispatched[0].status, [404, 404, "reader:404"]);
});

test("同じ回に同じ会社の発表が複数あれば1本だけ（新モデル優先）", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/google-ai.xml"].unshift({ title: "New tools for teachers", url: "https://ex.test/g-tools", at: T0 });
  h.feeds["https://feeds.test/gemini.xml"].unshift({ title: "Gemini 5 is now available", url: "https://ex.test/g5", at: T0 });
  const log = await h.run(T0 + 2 * MIN);
  assert.equal(h.calls.dispatches.length, 1);
  assert.equal(h.calls.dispatches[0].inputs.fast_url, "https://ex.test/g5");
  assert.equal(h.state().queue[await itemId("https://ex.test/g-tools")].status, "merged");
  assert.ok(log.queued.some((l) => l.startsWith("同じ会社")));
});

test("FAST_DRY_RUN=1 なら起動せずログだけ", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  const log = await h.run(T0 + 2 * MIN, { FAST_DRY_RUN: "1" });
  assert.equal(h.calls.dispatches.length, 0);
  assert.equal(log.wouldDispatch[0].url, "https://ex.test/gpt-7");
  assert.equal(h.state().queue[await itemId("https://ex.test/gpt-7")].status, "dry");
});

test("古い記事（max_age_hours より前）は起動しない", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 - 20 * 3600e3 });
  const log = await h.run(T0 + 2 * MIN);
  assert.equal(h.calls.dispatches.length, 0);
  assert.ok(log.new[0].includes("古い"));
});

test("速報レーンの実行が待機中なら起動を次の回に回す（通常の回の待機は気にしない）", async () => {
  const h = harness();
  await h.run(T0);
  h.world.runs = [{ status: "pending", display_title: `${RUN_PREFIX} https://ex.test/other`, created_at: new Date(T0).toISOString(), run_number: 7 }];
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  let log = await h.run(T0 + 2 * MIN);
  assert.equal(h.calls.dispatches.length, 0);
  assert.match(log.waiting, /待機中/);
  h.world.runs = [{ status: "pending", display_title: "Auto Article Pipeline (web)", created_at: new Date(T0).toISOString() }];
  log = await h.run(T0 + 4 * MIN);
  assert.equal(h.calls.dispatches.length, 1);
});

test("パイプラインの結果（state/fast_lane.json）が来たら完了にする", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  await h.run(T0 + 2 * MIN);
  const id = await itemId("https://ex.test/gpt-7");
  h.world.runs = [{ status: "in_progress", display_title: `${RUN_PREFIX} https://ex.test/gpt-7`, created_at: new Date(T0 + 2 * MIN).toISOString() }];
  await h.run(T0 + 4 * MIN);
  assert.equal(h.state().queue[id].status, "dispatched");
  h.world.acks = { [id]: { outcome: "created", slug: "gpt-7-launch", finishedAt: new Date(T0 + 7 * MIN).toISOString() } };
  const log = await h.run(T0 + 8 * MIN);
  assert.equal(h.state().queue[id].status, "done");
  assert.equal(h.state().queue[id].slug, "gpt-7-launch");
  assert.ok(log.done[0].includes("gpt-7-launch"));
  assert.equal(h.calls.dispatches.length, 1);
});

test("同じ記事の古い結果（今回の起動より前）は完了とみなさない", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  const id = await itemId("https://ex.test/gpt-7");
  h.world.acks = { [id]: { outcome: "duplicate", finishedAt: new Date(T0 - 3600e3).toISOString() } };
  await h.run(T0 + 2 * MIN);
  h.world.runs = [{ status: "in_progress", display_title: `${RUN_PREFIX} https://ex.test/gpt-7`, created_at: new Date(T0 + 2 * MIN).toISOString() }];
  await h.run(T0 + 4 * MIN);
  assert.equal(h.state().queue[id].status, "dispatched");
  h.world.acks = { [id]: { outcome: "created", slug: "gpt-7", finishedAt: new Date(T0 + 5 * MIN).toISOString() } };
  await h.run(T0 + 6 * MIN);
  assert.equal(h.state().queue[id].status, "done");
  assert.equal(h.state().queue[id].outcome, "created");
});

test("取り消し・結果なしなら起動し直し、max_dispatches 回で諦める", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  await h.run(T0 + 2 * MIN);
  const id = await itemId("https://ex.test/gpt-7");
  let t = T0 + 2 * MIN;
  for (let n = 1; n < RULES.max_dispatches; n += 1) {
    h.world.runs = [{ status: "completed", conclusion: "cancelled", display_title: `${RUN_PREFIX} https://ex.test/gpt-7`, created_at: new Date(t + 10000).toISOString() }];
    t += 4 * MIN;
    await h.run(t);
    assert.equal(h.calls.dispatches.length, n + 1, `再起動 ${n}`);
  }
  h.world.runs = [{ status: "completed", conclusion: "failure", display_title: `${RUN_PREFIX} https://ex.test/gpt-7`, created_at: new Date(t + 10000).toISOString() }];
  const log = await h.run(t + 4 * MIN);
  assert.equal(h.calls.dispatches.length, RULES.max_dispatches);
  assert.equal(h.state().queue[id].status, "gave_up");
  assert.ok(log.gaveUp.length === 1);
});

test("作れなかった（retry）なら実行の終了後に起動し直す", async () => {
  const h = harness();
  await h.run(T0);
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  await h.run(T0 + 2 * MIN);
  const id = await itemId("https://ex.test/gpt-7");
  h.world.acks = { [id]: { outcome: "retry", finishedAt: new Date(T0 + 3 * MIN).toISOString() } };
  h.world.runs = [{ status: "in_progress", display_title: `${RUN_PREFIX} https://ex.test/gpt-7`, created_at: new Date(T0 + 2 * MIN).toISOString() }];
  await h.run(T0 + 4 * MIN);
  assert.equal(h.calls.dispatches.length, 1);
  h.world.runs[0].status = "completed";
  h.world.runs[0].conclusion = "success";
  await h.run(T0 + 6 * MIN);
  assert.equal(h.calls.dispatches.length, 2);
});

test("1日の上限を超えた分は capped（起動しない）", async () => {
  const h = harness();
  await h.run(T0, { FAST_DAILY_MAX: "1" });
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  await h.run(T0 + 2 * MIN, { FAST_DAILY_MAX: "1" });
  h.feeds["https://feeds.test/google-ai.xml"].unshift({ title: "Introducing Gemini 5", url: "https://ex.test/g5", at: T0 });
  const log = await h.run(T0 + 4 * MIN, { FAST_DAILY_MAX: "1" });
  assert.equal(h.calls.dispatches.length, 1);
  assert.equal(h.state().queue[await itemId("https://ex.test/g5")].status, "capped");
  assert.equal(log.capped.length, 1);
});

test("ETag があれば条件付きで取得し、304 なら KV に書かない", async () => {
  const h = harness();
  h.world.etag["https://feeds.test/openai.xml"] = '"v1"';
  await h.run(T0);
  const before = h.store.get("state");
  const log = await h.run(T0 + 2 * MIN);
  const req = h.calls.requests.filter((r) => r.url === "https://feeds.test/openai.xml").at(-1);
  assert.equal(req.headers["If-None-Match"], '"v1"');
  assert.equal(log.notModified, 1);
  assert.equal(h.store.get("state"), before);
});

test("取得に失敗した発信元は既読の記録を消さない", async () => {
  const h = harness();
  h.feeds["https://feeds.test/openai.xml"].unshift({ title: "Introducing GPT-7", url: "https://ex.test/gpt-7", at: T0 });
  await h.run(T0);
  const seen = h.state().sources["openai-news"].seen;
  delete h.feeds["https://feeds.test/openai.xml"];
  const log = await h.run(T0 + 2 * MIN);
  assert.equal(log.errors["openai-news"], 404);
  assert.deepEqual(h.state().sources["openai-news"].seen, seen);
  assert.equal(h.calls.dispatches.length, 0);
});
