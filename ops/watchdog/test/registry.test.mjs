// 追加の発信元（scripts/sources_registry.json）のテスト。見出し・URL は架空のもの（実際の見出しは 2026-10 のもの）
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { buzzMatch, buzzStop, compile, due, similar, fastLane, mergeRegistry, parseHtmlList, relevant, WAIT_REASON } from "../src/fastlane.js";
import { compileRadar, recordBuzz } from "../src/radar.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const BASE = JSON.parse(readFileSync(join(ROOT, "scripts", "fast_lane_rules.json"), "utf-8"));
const REGISTRY = JSON.parse(readFileSync(join(ROOT, "scripts", "sources_registry.json"), "utf-8"));
const RULES = mergeRegistry(BASE, REGISTRY);
const R = compile(RULES);

test("登録の形: slug は重ならず、tier・種類・https・会社がそろっている", () => {
  const slugs = RULES.sources.map((s) => s.slug);
  assert.equal(new Set(slugs).size, slugs.length);
  for (const s of REGISTRY.sources) {
    assert.ok(["A", "B", "C"].includes(s.tier), s.slug);
    assert.ok(["rss", "html"].includes(s.type), s.slug);
    assert.ok(s.url.startsWith("https://"), s.slug);
    assert.ok(s.entity && s.company && s.name, s.slug);
    if (s.type === "html") assert.ok(s.link_re, s.slug);
    if (s.genre) assert.ok(RULES.genres[s.genre], `${s.slug}: genre ${s.genre}`);
  }
  // 元からの発信元は tier なし（毎回）のまま
  assert.ok(RULES.sources.filter((s) => !s.registry).every((s) => !s.tier));
});

test("見に行く間隔: A は毎回・B は10分に1回・C は30分に1回（1日の回数）", () => {
  const count = (slug) => {
    let n = 0;
    for (let m = 0; m < 1440; m += 2) if (due(R.bySlug[slug], new Date(Date.UTC(2026, 9, 28, 0, m)), R)) n += 1;
    return n;
  };
  assert.equal(count("openai-news"), 720);
  assert.equal(count("xai-news"), 720);
  assert.equal(count("cursor-blog"), 144);
  assert.equal(count("figma-blog"), 48);
});

const CASES = [
  // tier A: 発表の語があればすぐ
  ["xai-news", "Introducing Grok Voice 3.0", true],
  ["deepseek-news", "DeepSeek-V4.1-Flash-1017 Release 2026/10/17", true],
  ["nvidia-newsroom", "NVIDIA and Oracle Expand NVIDIA Vera Rubin to Multi-Gigawatt Scale", false],
  ["nvidia-newsroom", "NVIDIA Unveils Vera Rubin Ultra", true],
  ["about-amazon", "Amazon data center communities: Here's what's happening near you", false],
  // tier B・C: 強い語・新モデルはすぐ、発表の語だけなら話題待ち
  ["cursor-blog", "Introducing the Agent SDK", false],
  ["cohere-blog", "Cohere to acquire AISLE to advance cyber-resilient sovereign AI", true],
  ["cohere-blog", "Introducing Embed 5—A new family of frontier embedding models", true],
  ["github-changelog", "GitHub Copilot assisted permissions generally available", false],
  ["github-changelog", "GitHub Copilot supports server-to-server authentication", false],
  ["intel-newsroom", "Intel to Acquire Classiq to Create a Full-stack Quantum Computing Platform", true],
  ["hugging-face-blog", "Can we trust LLMs to judge whether a research idea is novel?", false],
  ["windows-blog", "Announcing new builds for 23 October 2026", false],
  ["elevenlabs-blog", "How to build an AI voice assistant: Brand-aligned voice AI", false],
  ["pfn-news", "国産生成AI基盤モデルPLaMo PrimeにWeb検索・Deep Research搭載", true],
  ["pfn-news", "日本総研とPFN、国産大規模言語モデル「PLaMo」のライセンス契約を締結", false],
  ["sakana-ai", "Taking Japan-Born AI Products to the World", false],
  // business: 決算・業績修正・M&A・社長交代など（配当・社債などの定例の開示は除く）
  ["softbank-group-press", "IR情報 2026年10月23日 剰余金の配当（中間配当）に関するお知らせ", false],
  ["softbank-group-press", "IR情報 2026年10月1日 OpenAIへの追加出資（サードトランシェ）の実行に関するお知らせ", true],
  ["softbank-group-press", "企業情報 2026年9月30日 DigitalBridgeの買収完了に関するお知らせ", true],
  ["toyota-news", "2027年3月期 第2四半期決算短信", true],
  ["toyota-news", "LEXUS、「LBX」を一部改良", false],
  ["honda-news", "「VEZEL」をマイナーモデルチェンジし発売", false],
  ["honda-news", "代表取締役の異動に関するお知らせ", true],
  ["rakuten-press", "「楽天市場」、2026年冬のトレンド予測を発表", false],
  ["mercari-press", "メルカリ、クイック・ネットワークと資本業務提携契約を締結", true],
  ["kddi-news-release", "業績予想の修正に関するお知らせ", true],
];

test("判定の結果（追加の発信元）", () => {
  for (const [source, title, expected] of CASES) assert.equal(relevant(title, source, R).ok, expected, `${source}: ${title}`);
  assert.equal(relevant("Introducing the Agent SDK", "cursor-blog", R).reason, WAIT_REASON);
});

test("判定が Python（scripts/fast_lane.py）と同じ（追加の発信元も読む）", () => {
  const input = CASES.map(([source, title]) => ({ source, title }));
  const r = spawnSync("python3", ["scripts/fast_lane.py", "--classify"], { input: JSON.stringify(input), cwd: ROOT, encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(CASES.map(([source, title]) => relevant(title, source, R)), JSON.parse(r.stdout));
});

test("一覧ページの文字から見出しを取る（同じ記事へのリンクはいちばん長い文字）", () => {
  const html = `<a href="/blog/rerank-5">Learn more</a><a href="/blog/rerank-5"><div>Introducing Rerank 5 for search</div></a>
    <a href="/blog/topic/product">Product topic page</a><a href="https://other.test/blog/x">External link here</a>`;
  const items = parseHtmlList(html, { url: "https://co.test/blog", link_re: "^/blog/(?!topic/)[a-z0-9-]+$", title_from: "text" });
  assert.deepEqual(items.map((i) => [i.url, i.title]), [["https://co.test/blog/rerank-5", "Introducing Rerank 5 for search"]]);
});

test("話題の突き合わせ: 同じ会社でも別の話題なら話題とみなさない（会社名の語は数えない）", () => {
  const stop = buzzStop(R);
  const re = /(?<![A-Za-z])Cursor(?![A-Za-z])|Anysphere/;
  const list = [{ at: "2026-10-28T00:00:00Z", t: "Cursor raises $2B at a $50B valuation", src: "Techmeme" }];
  assert.equal(buzzMatch("Introducing the Agent SDK", list, re, stop), null);
  list.push({ at: "2026-10-28T00:00:00Z", t: "Cursor launches an Agent SDK so developers can embed its coding agent", src: "Techmeme" });
  assert.deepEqual(buzzMatch("Introducing the Agent SDK", list, re, stop).shared, ["sdk"]);
});

// --------------------------------------------------------------------------- //
// 1回分の流れ（KV・フィード・GitHub は偽物）
// --------------------------------------------------------------------------- //

const TEST_RULES = mergeRegistry({ ...BASE, sources: [] }, {
  ...REGISTRY,
  sources: [
    { slug: "co-b", company: "Cursor", name: "B", type: "rss", url: "https://feeds.test/b.xml", tier: "B", entity: "cursor", buzz_re: "(?<![A-Za-z])Cursor(?![A-Za-z])" },
    { slug: "co-c", company: "Figma", name: "C", type: "rss", url: "https://feeds.test/c.xml", tier: "C", entity: "figma" },
  ],
});

function rss(items) {
  return `<rss><channel>${items.map((i) => `<item><title>${i.title}</title><link>${i.url}</link><pubDate>${new Date(i.at).toUTCString()}</pubDate></item>`).join("")}</channel></rss>`;
}

function harness() {
  const store = new Map();
  const feeds = {
    "https://feeds.test/b.xml": [{ title: "Old b", url: "https://ex.test/old-b", at: Date.parse("2026-10-20T00:00:00Z") }],
    "https://feeds.test/c.xml": [{ title: "Old c", url: "https://ex.test/old-c", at: Date.parse("2026-10-20T00:00:00Z") }],
  };
  const calls = { dispatches: [], polled: [] };
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
  const fetchImpl = async (url) => {
    if (!(url in feeds)) return new Response("<html></html>", { status: 200 });
    calls.polled.push(url);
    return new Response(rss(feeds[url]), { status: 200 });
  };
  const gh = async (path, init = {}) => {
    if (path.startsWith("/actions/workflows/auto_run.yml/runs")) return { workflow_runs: [] };
    if (path.startsWith("/contents/")) return JSON.stringify({ items: {} });
    if (path.endsWith("/dispatches")) {
      calls.dispatches.push(JSON.parse(init.body));
      return null;
    }
    if (path === "/issues") return { number: 1 };
    throw new Error(`unexpected ${path}`);
  };
  const run = (now) => fastLane(env, new Date(now), { rules: TEST_RULES, fetch: fetchImpl, gh });
  return { env, store, feeds, calls, run, state: () => JSON.parse(store.get("state")) };
}

// 2026-10-28 00:00 UTC から2分ごと。B・C が見に行く回を探す
const T0 = Date.UTC(2026, 9, 28, 0, 0);
const RT = compile(TEST_RULES);
const nextDue = (slug, from) => {
  for (let t = from; ; t += 2 * 60000) if (due(RT.bySlug[slug], new Date(t), RT)) return t;
};

test("tier B: 発表の語だけの見出しは話題待ち → まとめサイトに同じ話題が出たら起動・別の話題では起動しない", async () => {
  const h = harness();
  let t = nextDue("co-b", T0);
  await h.run(t); // 初回は既読にするだけ
  assert.equal(h.calls.polled.filter((u) => u.endsWith("b.xml")).length, 1);
  await h.run(t + 2 * 60000); // B は次の回には見に行かない
  assert.equal(h.calls.polled.filter((u) => u.endsWith("b.xml")).length, 1);

  h.feeds["https://feeds.test/b.xml"].unshift({ title: "Introducing the Agent SDK", url: "https://ex.test/agent-sdk", at: t + 60000 });
  t = nextDue("co-b", t + 2 * 60000);
  let log = await h.run(t);
  assert.equal(h.calls.dispatches.length, 0);
  assert.ok(log.new.some((l) => l.includes(WAIT_REASON)));
  assert.equal(Object.keys(h.state().pending).length, 1);

  // 別の話題（資金調達）では起動しない
  await h.env.FAST.put("buzz", JSON.stringify({ cursor: [{ at: new Date(t).toISOString(), t: "Cursor raises $2B", src: "Techmeme" }] }));
  await h.run(t + 2 * 60000);
  assert.equal(h.calls.dispatches.length, 0);

  // 同じ話題が出たら（Cursor の見張りの回でなくても）起動する
  await h.env.FAST.put("buzz", JSON.stringify({ cursor: [{ at: new Date(t).toISOString(), t: "Cursor launches Agent SDK for its coding agent", src: "Techmeme" }] }));
  log = await h.run(t + 4 * 60000);
  assert.equal(h.calls.dispatches.length, 1);
  assert.equal(h.calls.dispatches[0].inputs.fast_url, "https://ex.test/agent-sdk");
  assert.match(h.state().queue[Object.keys(h.state().queue)[0]].reason, /話題（Techmeme）/);
  assert.equal(Object.keys(h.state().pending).length, 0);
});

test("tier B: 話題にならないまま buzz_hours 時間たったら話題待ちをやめる", async () => {
  const h = harness();
  let t = nextDue("co-b", T0);
  await h.run(t);
  h.feeds["https://feeds.test/b.xml"].unshift({ title: "Introducing Projects", url: "https://ex.test/projects", at: t + 60000 });
  t = nextDue("co-b", t + 2 * 60000);
  await h.run(t);
  assert.equal(Object.keys(h.state().pending).length, 1);
  await h.run(t + (REGISTRY.buzz_hours * 60 + 2) * 60000);
  assert.equal(Object.keys(h.state().pending).length, 0);
  assert.equal(h.calls.dispatches.length, 0);
});

test("tier C: 強い語（買収）ならすぐ起動する", async () => {
  const h = harness();
  let t = nextDue("co-c", T0);
  await h.run(t);
  h.feeds["https://feeds.test/c.xml"].unshift({ title: "Figma to acquire Example Labs", url: "https://ex.test/acq", at: t + 60000 });
  t = nextDue("co-c", t + 2 * 60000);
  assert.ok(t - T0 >= 30 * 60000);
  await h.run(t);
  assert.equal(h.calls.dispatches.length, 1);
  assert.equal(h.state().queue[Object.keys(h.state().queue)[0]].reason, "大きな発表");
});

test("レーダーが会社の名前の出た見出しを KV の buzz に残す（古い見出し・重複は残さない・新しいものが無ければ書かない）", async () => {
  const RR = compileRadar(TEST_RULES);
  const store = new Map();
  let puts = 0;
  const env = { FAST: { get: async (k) => (store.has(k) ? JSON.parse(store.get(k)) : null), put: async (k, v) => { puts += 1; store.set(k, v); } } };
  const now = new Date(T0);
  const items = [
    { title: "Cursor launches Agent SDK", publishedAt: new Date(T0 - 3600e3).toISOString(), sourceName: "Techmeme" },
    { title: "Cursor launches Agent SDK", publishedAt: new Date(T0 - 3600e3).toISOString(), sourceName: "Techmeme" },
    { title: "Old Cursor story", publishedAt: new Date(T0 - 20 * 3600e3).toISOString(), sourceName: "Techmeme" },
    { title: "A cursor bug in Windows", publishedAt: new Date(T0).toISOString(), sourceName: "HN" },
  ];
  assert.equal(await recordBuzz(env, items, RR, now), 1);
  assert.deepEqual(JSON.parse(store.get("buzz")).cursor.map((b) => b.t), ["Cursor launches Agent SDK"]);
  assert.equal(await recordBuzz(env, items, RR, now), 0);
  assert.equal(puts, 1);
});

test("同じ会社の同じ発表が別の URL で載ったもの（ブログとニュースルーム）は2本目を見送る", async () => {
  const stop = buzzStop(R);
  assert.ok(similar("NVIDIA Unveils Minerva to Bring End-to-End Observability for AI Factories", "NVIDIA Unveils Minerva to Bring End-to-End Observability for AI Factories | NVIDIA Newsroom", stop));
  assert.ok(!similar("NVIDIA Unveils Minerva for AI Factories", "NVIDIA cuDSS Now Generally Available to Accelerate Engineering", stop));
  // 流れ: 登録済みの発表と同じ見出しが別の URL で来ても起動しない
  const h = harness();
  let t = nextDue("co-b", T0);
  await h.run(t);
  h.feeds["https://feeds.test/b.xml"].unshift({ title: "Cursor to acquire Example Labs", url: "https://ex.test/acq-1", at: t + 60000 });
  t = nextDue("co-b", t + 2 * 60000);
  await h.run(t);
  assert.equal(h.calls.dispatches.length, 1);
  h.feeds["https://feeds.test/b.xml"].unshift({ title: "Cursor to acquire Example Labs | Newsroom", url: "https://ex.test/acq-2", at: t + 60000 });
  t = nextDue("co-b", t + 2 * 60000);
  const log = await h.run(t);
  assert.ok(log.queued.some((l) => l.startsWith("登録済みの発表と同じ")));
  assert.ok(h.calls.dispatches.every((d) => d.inputs.fast_url === "https://ex.test/acq-1"));
});
