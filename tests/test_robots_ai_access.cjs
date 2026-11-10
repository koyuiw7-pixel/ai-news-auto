const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// LLMO-A2: AI検索の巡回（SEARCH_AGENTS）は、いつでも記事・ガイド・道具・サイトマップ・フィードを読めること（オーナーの指示）。
// 学習用の巡回（TRAINING_CRAWLERS）の扱いはオーナーが決める（B1）。決まるまでは今と同じ許可のまま。
const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "app/robots.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText;
const loaded = new Module(sourcePath, module);
loaded.filename = sourcePath;
loaded.paths = Module._nodeModulePaths(root);
const realRequire = loaded.require.bind(loaded);
loaded.require = (id) => (id === "@/site.config" ? { siteConfig: { url: "https://ai-tech-express.jp" } } : realRequire(id));
loaded._compile(compiled, sourcePath);
const robots = loaded.exports.default();

const SEARCH_AGENTS = [
  "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User", "Claude-SearchBot", "Claude-User",
  "Bingbot", "DuckAssistBot", "MistralAI-User", "MistralAI-Index",
];
const TRAINING_CRAWLERS = ["GPTBot", "ClaudeBot", "Google-Extended", "Applebot-Extended", "MistralAI-Training"];
const PATHS = ["/articles/x", "/guides/x", "/tools/x", "/sitemap.xml", "/feed.xml"];

const list = (value) => (value === undefined ? [] : Array.isArray(value) ? value : [value]);

// RFC 9309: その名前のグループがあればそれ、なければ * のグループ。いちばん長く一致した行が勝ち、同じ長さなら Allow が勝つ
function groupFor(agent) {
  const named = robots.rules.find((rule) => list(rule.userAgent).some((ua) => ua.toLowerCase() === agent.toLowerCase()));
  return named || robots.rules.find((rule) => list(rule.userAgent).includes("*"));
}
function allowed(rule, url) {
  const hits = [
    ...list(rule.allow).filter((p) => url.startsWith(p)).map((p) => [p.length, true]),
    ...list(rule.disallow).filter((p) => p && url.startsWith(p)).map((p) => [p.length, false]),
  ].sort((a, b) => b[0] - a[0] || Number(b[1]) - Number(a[1]));
  return hits.length === 0 || hits[0][1];
}

test("AI検索の巡回は、名前つきのグループで記事・ガイド・道具・サイトマップ・フィードを読める", () => {
  for (const agent of SEARCH_AGENTS) {
    const rule = groupFor(agent);
    assert.ok(list(rule.userAgent).includes(agent), `${agent} が robots.ts の SEARCH_AGENTS にない`);
    assert.ok(list(rule.allow).includes("/"), `${agent} に Allow: / がない`);
    assert.ok(!list(rule.disallow).includes("/"), `${agent} に Disallow: / がある（AIの回答に引用されなくなる）`);
    for (const url of PATHS) assert.ok(allowed(rule, url), `${agent} が ${url} を読めない`);
  }
});

test("どのグループにも、むき出しの Disallow: / を書かない（* も同じ）", () => {
  for (const rule of robots.rules) {
    assert.ok(!list(rule.disallow).includes("/"), `${list(rule.userAgent).join(", ")} に Disallow: / がある`);
  }
  for (const url of PATHS) assert.ok(allowed(groupFor("Googlebot"), url), `* のグループで ${url} が読めない`);
});

test("学習用の巡回は、オーナーが決めるまで今と同じ許可（Allow: / と /api/・/review だけ止める）", () => {
  for (const agent of TRAINING_CRAWLERS) {
    const rule = groupFor(agent);
    assert.ok(list(rule.userAgent).includes(agent), `${agent} が robots.ts の TRAINING_CRAWLERS にない`);
    assert.deepEqual(list(rule.allow), ["/"]);
    assert.deepEqual(list(rule.disallow), ["/api/", "/review"]);
  }
  // 検索の巡回と学習の巡回は別のグループ（学習の扱いだけをあとで変えられるように）
  assert.notEqual(groupFor("OAI-SearchBot"), groupFor("GPTBot"));
});

test("robots.ts のコメントに、検索の巡回は常に許可・学習の巡回はオーナーが決めることが書いてある", () => {
  assert.match(source, /SEARCH_AGENTS: [^\n]*いつでも許可する/);
  assert.match(source, /TRAINING_CRAWLERS: [^\n]*オーナーが決める/);
});
