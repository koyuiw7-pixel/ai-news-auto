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
const offers = load(path.join(root, "lib/offers.ts"));
const actionAd = load(path.join(root, "lib/action-ad.ts"));

// 2026-11-22 オーナー「任せる」: W48 災害・事故の記事に火災保険の広告を出さない／W49 トップの主な枠に 800字未満の記事を置かない
const now = Date.parse("2026-11-22T09:00:00Z");
const art = (slug, bodyChars, fields = {}) => ({
  slug, bodyChars, title: `電気代の値引き ${slug}`, genreSlug: "public", tags: [], keywords: [], channelSlug: "", sourceUrl: "",
  photo: { src: "/img/a.jpg" }, publishedAt: new Date(now - 3_600_000).toISOString(), generatedAt: new Date(now - 3_600_000).toISOString(), ...fields,
});

test("W49: 800字未満は主な枠に置かない。800字ちょうどは置く", () => {
  assert.equal(home.homeFeatureable({ bodyChars: 799 }), false);
  assert.equal(home.homeFeatureable({ bodyChars: 800 }), true);
  const all = [art("short", 300), art("long", 1200)];
  assert.deepEqual(home.preferFeatured(all, (pool) => pool.map((a) => a.slug)), ["long"]);
});

test("W49: 長い記事が無い日は枠を空にしない", () => {
  assert.deepEqual(home.preferFeatured([art("short", 300)], (pool) => pool.map((a) => a.slug)), ["short"]);
});

test("W49: ストーリーの丸から短い記事を外し、空の丸は出さない", () => {
  const all = [art("short", 300), art("long", 1200)];
  const out = home.featuredBundles([{ key: "a", items: [{ slug: "short" }, { slug: "long" }] }, { key: "b", items: [{ slug: "short" }] }], all);
  assert.deepEqual(out.map((b) => [b.key, b.items.map((i) => i.slug)]), [["a", ["long"]]]);
});

test("W49: トップのページが主な枠すべてで同じ判定を使う", () => {
  const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
  for (const needle of ["pickHomeLead(all.filter(homeFeatureable))", "preferFeatured(all, (pool) => pickHomeHeadlines", "pickTrendingStrip(all.filter(homeFeatureable)",
    "preferFeatured(all, (pool) => pickLifeMoney", "preferFeatured(ai,", "featuredBundles(getStoryRailBundles(), all)"]) assert.ok(page.includes(needle), needle);
});

test("W48: 災害・事故の題名は保険の広告を止める。保険そのものの記事は止めない", () => {
  for (const title of ["台風で大規模な停電", "住宅火災で2人死亡", "高速道路で多重事故", "工場で爆発、避難指示", "静岡県西部の地震、余震は1週間程度に注意　罹災証明書と地震保険の確認点"]) assert.equal(offers.insuranceAdBlocked({ title }), true, title);
  for (const title of ["火災保険料、来年度から平均で値上げ", "地震保険の保険料が改定", "地震保険料は5万円まで全額、超えても控除は一律5万円", "電気代の値引きが開始"]) assert.equal(offers.insuranceAdBlocked({ title }), false, title);
});

test("W48: 行動欄の広告は保険だけを除き、防災用品は残す", () => {
  const rule = { key: "disaster", title: "備え", match: "停電", partners: ["bang-kasai", "jackery"], max: 2 };
  const article = { ...art("outage", 1200, { title: "停電 停電の備え", tags: ["停電"], keywords: ["停電"] }), description: "停電", lede: "停電" };
  const pick = (key) => ({ item: { key } });
  const ad = actionAd.actionAdForArticle(article, [], pick, [rule]);
  assert.deepEqual(ad.items.map((x) => x.item.key), ["jackery"]);
});
