// 2026-11-21 オーナー「広告の無いページも合う提携先で埋めて」:
// 今ある提携先のうち、記事の品物・場面に本当に合うものだけを足す（合うものが無ければ空のまま。既定の広告では埋めない）。
// 回収・事故・流出・災害など読者が困っている記事に、通販や他社の広告を出さない。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
process.chdir(root);
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  cache.set(file, mod);
  const original = mod.require.bind(mod);
  mod.require = (name) => {
    if (name === "@/lib/content-fs") return fs;
    if (name === "@/lib/articles") return { getAllArticles: () => [] };
    if (name.startsWith("@/lib/")) return load(path.join(root, "lib", `${name.slice(6)}.ts`));
    if (name.startsWith("./")) return load(path.join(path.dirname(file), `${name}.ts`));
    return original(name);
  };
  mod._compile(compiled, file);
  return mod.exports;
}
const { offerPlanForArticle, afterBodyOffer } = load(path.join(root, "lib/offers.ts"));
const offers = JSON.parse(fs.readFileSync(path.join(root, "content/offers.json"), "utf8"));
const base = { slug: "t", title: "", seoTitle: "", lede: "", description: "", highlights: [], tags: [], keywords: [], genreSlug: "lifestyle", channelSlug: "", sourceName: "" };
const box = (fields) => {
  const shown = afterBodyOffer(offerPlanForArticle({ ...base, ...fields }, [], []), true);
  return shown && !String(shown.topic ?? "").startsWith("fallback-") ? shown : undefined;
};
const NEW_TOPICS = ["shop-coffee", "power-bill", "mobile-plan", "tax-business", "design-learn", "local-model", "trip-plan"];

test("合う記事に、合う提携先が出る", () => {
  const cases = [
    [{ title: "九州電力12月分、従量電灯Bは下がる" }, "power-bill", "elpio"],
    [{ title: "「スマホデビュープラン2」の条件" }, "mobile-plan", "bb-excite"],
    [{ title: "飲食料品の消費税が1%に　事業者の届出特例も", genreSlug: "public" }, "tax-business", "freee"],
    [{ title: "Canva、iPad版「Affinity」を公開", genreSlug: "tech-gadget" }, "design-learn", "coloso"],
    [{ title: "Gemma 4のPLEとは", genreSlug: "ai" }, "local-model", "gmktec"],
    [{ title: "Googleマップで旅程作成", genreSlug: "ai" }, "trip-plan", "jalan"],
  ];
  for (const [fields, topic, partner] of cases) {
    const shown = box(fields);
    assert.equal(shown?.topic, topic, fields.title);
    assert.ok(shown.items.some((item) => item.key === partner), fields.title);
  }
});

test("店の食品・製品の記事は、同じ種類の検索に案内する", () => {
  assert.ok(box({ title: "セブン-イレブンの中華まん2個で60円引き" }).items[0].name.includes("冷凍 中華まん"));
  assert.ok(box({ title: "ローソン、ロールケーキ214円" }).items[0].name.includes("ロールケーキ"));
  assert.ok(box({ title: "「VAIO F14」11月27日発売", genreSlug: "lifestyle" }).items[0].name.includes("ノートパソコン"));
  assert.ok(box({ title: "Apple、新iMacを発表", genreSlug: "tech-gadget" }).items[0].name.includes("iMac"));
});

test("回収・事故・流出・被害の記事には、新しい話題も通販の検索も出さない", () => {
  for (const title of [
    "ロールケーキを自主回収　賞味期限の誤り",
    "ハンバーガー店で食中毒　20人に症状",
    "牛丼店で強盗、逮捕",
    "V60ドリッパーを回収　破損のおそれ",
    "VAIOのバッテリーを回収　発火のおそれ",
    "九州電力12月分の検針で障害",
  ]) {
    assert.equal(box({ title }), undefined, title);
  }
});

test("流出の記事に旅行の広告を出さない", () => {
  assert.notEqual(box({ title: "Googleマップの旅程で個人情報が流出", genreSlug: "ai" })?.topic, "trip-plan");
});

test("米国だけの旅程サービスに、国内の宿の広告を出さない", () => {
  assert.equal(box({ title: "Googleの「Tabletop」は旅程や割り勘をAIが作る　米国18歳以上は順番待ち", genreSlug: "ai" })?.topic === "trip-plan", false);
});

test("新しい話題は、ほかの話題が当たらないときだけ使い、今ある提携先だけを使う", () => {
  for (const key of NEW_TOPICS) {
    const topic = offers.topics.find((t) => t.key === key);
    assert.ok(topic, key);
    assert.equal(topic.lastResort, true, key);
    assert.equal(topic.titleOnly, true, key);
    assert.ok(new RegExp(topic.articleExclude).test("宝くじ"), key);
    assert.ok(new RegExp(topic.articleExclude).test("自主回収"), key);
    for (const partner of topic.partners) assert.ok(offers.partners[partner] && !offers.partners[partner].hidden, `${key}: ${partner}`);
  }
});
