const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// トップの見出しの欄に、話題の記事（話題のレーン・Muse に頼んだ記事。載せて24時間以内）を分野で隠さずに出す（lib/home-lead.ts。2026-11-13 オーナー「Googleからの流入対策」）
const root = path.resolve(__dirname, "..");
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  if (file.endsWith(".json")) return JSON.parse(fs.readFileSync(file, "utf8"));
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  cache.set(file, mod);
  const original = mod.require.bind(mod);
  mod.require = (name) => {
    if (name.startsWith("@/") || name.startsWith(".")) {
      const base = name.startsWith("@/") ? path.join(root, name.slice(2)) : path.resolve(path.dirname(file), name);
      for (const ext of ["", ".ts", ".tsx", ".json"]) if (fs.existsSync(base + ext) && fs.statSync(base + ext).isFile()) return load(base + ext);
    }
    return original(name);
  };
  mod._compile(compiled, file);
  return mod.exports;
}
const home = load(path.join(root, "lib/home-lead.ts"));

const now = Date.parse("2026-11-13T09:30:00Z");
const hoursAgo = (h) => new Date(now - h * 3_600_000).toISOString();
const base = { type: undefined, tags: [], keywords: [], channelSlug: "", sourceUrl: "", photo: { src: "/img/a.jpg" }, publishedAt: hoursAgo(1), generatedAt: hoursAgo(1) };
const art = (slug, fields) => ({ ...base, slug, ...fields });

const money = Array.from({ length: 8 }, (_, i) =>
  art(`money-${i}`, { title: `電気代の値引き、${i + 1}月使用分から開始　申請は不要`, genreSlug: "public", generatedAt: hoursAgo(i + 1) }),
);
const kohakuList = art("kohaku-list", { title: "紅白歌合戦2026 出場歌手41組の一覧　初出場は7組", genreSlug: "lifestyle", writer: "muse", tags: ["テレビ", "年末年始"], keywords: ["紅白歌合戦2026"], generatedAt: hoursAgo(5) });
const kohakuChanges = art("kohaku-changes", { title: "紅白の出場41組、去年から20組が入れ替わる", genreSlug: "entertainment", writer: "muse", tags: ["テレビ", "音楽"], keywords: ["紅白歌合戦2026"], generatedAt: hoursAgo(2) });
const sumo = art("sumo", { title: "大相撲九州場所6日目の勝敗と注目取組", genreSlug: "sports", trendKeyword: "大相撲九州場所", generatedAt: hoursAgo(0.5) });
const oldTrend = art("old-trend", { title: "大相撲九州場所4日目の勝敗", genreSlug: "sports", trendKeyword: "大相撲九州場所", generatedAt: hoursAgo(30) });
const aiNews = art("ai-news", { title: "OpenAI、開発者向けの新しいAPIを公開", genreSlug: "ai", generatedAt: hoursAgo(1) });
const all = [sumo, ...money, kohakuChanges, kohakuList, aiNews, oldTrend].sort((a, b) => Date.parse(b.generatedAt) - Date.parse(a.generatedAt));

test("話題の記事は分野を問わない。24時間を過ぎた記事・印の無い記事は話題の記事にしない", () => {
  assert.equal(home.isTrendingFresh(sumo, now), true);
  assert.equal(home.isTrendingFresh(kohakuChanges, now), true);
  assert.equal(home.isTrendingFresh(oldTrend, now), false);
  assert.equal(home.isTrendingFresh(aiNews, now), false);
  assert.equal(home.isTrendingFresh({ ...kohakuList, duplicateOf: "x" }, now), false);
});

test("見出しの欄: 暮らしとお金の6本はそのまま、その後ろに話題の記事を話題ごとに1本（紅白は最初に載せた一覧が代表）", () => {
  const heads = home.pickHomeHeadlines(all, new Set(), 6, now).map((a) => a.slug);
  assert.deepEqual(heads.slice(0, 6), money.slice(0, 6).map((a) => a.slug));
  assert.deepEqual(heads.slice(6), ["kohaku-list", "sumo"]);
  assert.ok(!heads.includes("kohaku-changes") && !heads.includes("ai-news") && !heads.includes("old-trend"));
});

test("話題の記事が無い日は今までどおり6本。席は TRENDING_SLOTS 本まで", () => {
  const plain = home.pickHomeHeadlines(money, new Set(), 6, now);
  assert.equal(plain.length, 6);
  const many = Array.from({ length: 6 }, (_, i) => art(`trend-${i}`, { title: `話題${"あいうえおか"[i]}の試合の結果`, genreSlug: "sports", trendKeyword: `話題${i}`, generatedAt: hoursAgo(i + 1) }));
  const heads = home.pickHomeHeadlines([...many, ...money], new Set(), 6, now);
  assert.equal(heads.length, 6 + home.TRENDING_SLOTS);
});

test("写真の列: 話題の記事は暮らしとお金の分野でなくても候補に入る（写真のある記事だけ）", () => {
  const cards = home.pickLifeMoney([sumo, { ...kohakuChanges, photo: undefined }, ...money.slice(0, 2)], new Set(), 8, now).map((a) => a.slug);
  assert.ok(cards.includes("sumo"));
  assert.ok(!cards.includes("kohaku-changes"));
});

test("索引は書き手（writer）を持つ（Muse の記事の判定に使う）", () => {
  const src = fs.readFileSync(path.join(root, "lib/article-index.mjs"), "utf8");
  assert.match(src, /writer: a\.writer \|\| \(a\.museFile \? "muse" : undefined\)/);
  assert.match(fs.readFileSync(path.join(root, "app/page.tsx"), "utf8"), /pickHomeHeadlines\(all, new Set\(\[lead\.slug\]\), 6\)/);
});
