// 2026-11-17: AdSense の審査の期間（lib/ad-review.ts）は PR の囲みが本文の後ろの1つだけ。
// その囲みに本文中の枠の「残り」（inline）だけを渡していたので、候補が3つ以下の記事では右側に全部回って囲みが空になり、
// PR が1つも出ない記事があった（例: 進研ゼミのイヤホン回収の記事）。審査の期間は記事に合う候補をすべて（offer）渡す。
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
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const articleJson = (slug) => {
  const file = path.join(root, "content/articles", `${slug}.json`);
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : undefined;
};
const keys = (offer) => (offer?.items ?? []).map((item) => item.key);
const item = (key) => ({ key, kind: "partner", name: key, url: `https://px.a8.net/${key}`, topic: "t" });
const box = (items) => ({ topic: "t", eyebrow: "", headline: "h", lead: "", items, pixels: [] });

test("候補が3つ以下（右側に全部回り inline が空）でも、審査の期間は本文の後ろの囲みに候補をすべて出す", () => {
  const all = [item("a"), item("b"), item("c")];
  const plan = { offer: box(all), rail: box(all), inline: undefined };
  assert.deepEqual(keys(afterBodyOffer(plan, true)), ["a", "b", "c"]);
  // 審査の期間でなければ今までどおり本文中の枠（右側と重ならない残り）
  assert.equal(afterBodyOffer(plan, false), undefined);
  const plan6 = { offer: box([...all, item("d"), item("e"), item("f")]), rail: box(all), inline: box([item("d"), item("e"), item("f")]) };
  assert.deepEqual(keys(afterBodyOffer(plan6, false)), ["d", "e", "f"]);
  // 審査の期間は右側の1〜3位（いちばん合う候補）が先頭
  assert.deepEqual(keys(afterBodyOffer(plan6, true)).slice(0, 3), ["a", "b", "c"]);
});

test("候補が1つだけでも出す・候補が無ければ出さない", () => {
  assert.deepEqual(keys(afterBodyOffer({ offer: box([item("a")]), rail: box([item("a")]) }, true)), ["a"]);
  assert.equal(afterBodyOffer({}, true), undefined);
  assert.equal(afterBodyOffer({ offer: box([]) }, true), undefined);
});

test("実データ: 候補が少ない記事（イヤホン回収の記事）は、審査の期間の囲みが空にならない", (t) => {
  const a = articleJson("shinken-zemi-earphone-recall-pth077b");
  if (!a) return t.skip("記事が無い");
  const plan = offerPlanForArticle(a, [], []);
  assert.ok(plan.offer && plan.offer.items.length > 0 && plan.offer.items.length < 4, "候補は1〜3つ");
  assert.equal(plan.inline, undefined, "今までの inline は空（これが原因）");
  const shown = afterBodyOffer(plan, true);
  assert.deepEqual(keys(shown), keys(plan.offer));
});

test("実データ: ナゲットの記事は候補が5つあり、審査の期間の囲みにすべて渡る（話題は暮らしの既定の広告）", (t) => {
  const a = articleJson("mcdonalds-mcnugget-15pc-490yen");
  if (!a) return t.skip("記事が無い");
  const plan = offerPlanForArticle(a, [], []);
  const shown = afterBodyOffer(plan, true);
  assert.ok(shown && shown.items.length >= 2);
  assert.deepEqual(keys(shown), keys(plan.offer));
  // 新しい見た目（layout: noir）では、話題が当たらない既定の広告（fallback-*）は出さない決まり（2026-11-10 オーナー承認）。
  // この記事はその決まりで本番に出ていない。決まりは変えていない
  assert.equal(a.layout, "noir");
  assert.match(String(shown.topic), /^fallback-/);
  assert.ok(read("components/noir/noirArticlePage.tsx").includes('startsWith("fallback-") ? o : undefined'));
});

test("「既定の広告で埋めない」話題・14日間訪問0の記事は、今までどおり出さない", () => {
  // 計画が空（noFallback の話題、noPr の記事は page.tsx で空の計画）なら囲みも無い
  assert.equal(afterBodyOffer({ offer: undefined, rail: undefined, inline: undefined }, true), undefined);
  const page = read("app/articles/[slug]/page.tsx");
  assert.ok(page.includes("const offerPlan = noPr\n    ? { offer: undefined, rail: undefined, inline: undefined }"));
});

test("審査の期間の囲みは、今までの候補（同じ絞り込み済みの一覧）の中からだけ選ぶ", () => {
  const dir = path.join(root, "content/articles");
  let checked = 0;
  for (const f of fs.readdirSync(dir).slice(0, 300)) {
    let a;
    try { a = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")); } catch { continue; }
    if (!a.slug) continue;
    const plan = offerPlanForArticle(a, [], []);
    const shown = afterBodyOffer(plan, true);
    if (!plan.offer) { assert.equal(shown, undefined); continue; }
    const pool = new Set(keys(plan.offer));
    for (const k of keys(shown)) assert.ok(pool.has(k), `${a.slug}: ${k}`);
    assert.ok(shown && shown.items.length > 0, `${a.slug}: 候補があるのに囲みが空`);
    checked++;
  }
  assert.ok(checked > 50);
});

test("記事のページ: 審査の期間は afterBodyOffer で本文の後ろの1つの囲みを作る（右側・途中・上は出さないまま）", () => {
  const page = read("app/articles/[slug]/page.tsx");
  assert.ok(page.includes("const inlineOffer = offerWithBenefits(afterBodyOffer(offerPlan, adReview), benefitContext);"));
  assert.ok(page.includes("const offer = adReview ? undefined"));
  assert.ok(page.includes("{bodyTail && !adReview && inlineOffer && ("));
});
