// 2026-11-21 オーナー「提携先増やして」「無関係な広告で埋めない」:
// 新しい提携先14件は合う記事だけに出す。保険は病気・死亡・災害・事故・犯罪の記事に出さない。
// 既定の広告は記事ページに出さず、回収の記事に同じ種類の通販の検索を出さない。
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
const { offerPlanForArticle, afterBodyOffer, relevantOffer, relevantPlan } = load(path.join(root, "lib/offers.ts"));
const { shopLinkForArticle } = load(path.join(root, "lib/amazon.ts"));
const offers = JSON.parse(fs.readFileSync(path.join(root, "content/offers.json"), "utf8"));
const links = JSON.parse(fs.readFileSync(path.join(root, "affiliate_links.json"), "utf8"));
const base = { slug: "t", title: "", seoTitle: "", lede: "", description: "", highlights: [], tags: [], keywords: [], genreSlug: "lifestyle", channelSlug: "", sourceName: "" };
const shown = (fields) => relevantOffer(afterBodyOffer(offerPlanForArticle({ ...base, ...fields }, [], []), true));
const NEW = { "hoken-ai": "s00000025154001", "hoken-laundry": "s00000017634001", "minna-seimei": "s00000009416001", "wowow-od": "s00000025070001", techgo: "s00000024757003", myvision: "s00000024757001", itojuku: "s00000011467001", enechange: "s00000020286001", looop: "s00000020901002", enepoke: "s00000027749001", "keiei-plus-a": "s00000026111001", "xserver-business": "s00000001642023", "mobile-hoken": "s00000019424001", oisix: "s00000000488017" };
const INSURANCE_TOPICS = ["consult-pension", "consult-insurance", "phone-repair"];

test("新しい提携先は、決まった形のリンクと計測タグを持つ", () => {
  for (const [key, id] of Object.entries(NEW)) {
    const partner = offers.partners[key];
    assert.equal(partner?.programId, id, key);
    const a8mat = partner.link.replace("https://px.a8.net/svt/ejp?a8mat=", "");
    assert.match(a8mat, /^[0-9A-Z]+\+[0-9A-Z]+\+[0-9A-Z]+\+[0-9A-Z]+$/, key);
    assert.match(links[partner.program].pixel, new RegExp(`^https://www\\d+\\.a8\\.net/0\\.gif\\?a8mat=${a8mat.replaceAll("+", "\\+")}$`), key);
  }
});

test("公式で確かめていない宣伝文句を文面に使わない", () => {
  for (const key of Object.keys(NEW)) {
    const text = JSON.stringify([offers.partners[key].name, offers.partners[key].label, offers.partners[key].note, offers.partners[key].pitch]);
    assert.doesNotMatch(text, /\d|還元|全額|保証|即日|最安|おすすめ|No\.1|最大/, key);
  }
});

test("合う記事に、合う提携先が出る", () => {
  const cases = [
    [{ title: "相続の期限は短い順に3つ", genreSlug: "public" }, "hoken-ai"],
    [{ title: "年金は12月15日に2か月分を振り込み", genreSlug: "public" }, "hoken-ai"],
    [{ title: "電気・ガス代の動向", genreSlug: "lifestyle" }, "enechange"],
    [{ title: "プロパンガス料金の平均", genreSlug: "lifestyle" }, "enepoke"],
    [{ title: "行政書士試験の合格発表", genreSlug: "public" }, "itojuku"],
    [{ title: "ITエンジニアの転職市場", genreSlug: "business" }, "techgo"],
    [{ title: "個人事業主から法人化する目安", genreSlug: "business" }, "keiei-plus-a"],
    [{ title: "スマホの画面割れ、修理代の目安", genreSlug: "lifestyle" }, "mobile-hoken"],
    [{ title: "ミールキットの利用が増加", genreSlug: "lifestyle" }, "oisix"],
  ];
  for (const [fields, partner] of cases) assert.ok(shown(fields)?.items.some((item) => item.key === partner), fields.title);
});

test("保険の広告は、病気・死亡・災害・事故・犯罪の記事に出さない", () => {
  for (const word of ["がん", "死亡", "地震", "事故", "詐欺", "入院", "認知症"]) {
    for (const topic of INSURANCE_TOPICS) {
      assert.ok(new RegExp(offers.topics.find((t) => t.key === topic).articleExclude).test(word), `${topic}: ${word}`);
    }
  }
  for (const title of ["相続税の申告中に死亡事故", "年金受給者を狙う詐欺で逮捕", "がん保険の見直し", "スマホの水没事故"]) {
    const keys = shown({ title, genreSlug: "public" })?.items.map((item) => item.key) ?? [];
    for (const key of ["hoken-ai", "hoken-laundry", "minna-seimei", "mobile-hoken"]) assert.ok(!keys.includes(key), title);
  }
});

test("食品の回収・混入の記事に Oisix を出さない", () => {
  for (const title of ["ミールキットを自主回収", "食材宅配の商品に異物混入", "ミールキットで食中毒"]) {
    assert.ok(!shown({ title })?.items.some((item) => item.key === "oisix"), title);
  }
});

test("回収の記事に、同じ種類の通販の検索を出さない", () => {
  for (const title of ["イヤホンを自主回収　異常発熱", "電動アシスト自転車バッテリーで火災　回収率71%", "タイヤ7,029本をリコール"]) {
    const plan = offerPlanForArticle({ ...base, title }, [], []);
    assert.ok(!relevantOffer(plan.offer), title);
    assert.equal(shopLinkForArticle({ ...base, title }), undefined, title);
  }
});

test("記事ページは既定の広告を出さない", () => {
  assert.equal(relevantOffer({ topic: "fallback-life" }), undefined);
  assert.equal(relevantOffer({ topic: "power-bill" }).topic, "power-bill");
  const page = fs.readFileSync(path.join(root, "app/articles/[slug]/page.tsx"), "utf8");
  assert.ok(page.includes("relevantPlan(offerPlanForArticle("));
  assert.ok(page.includes("bodyTail && !onlyDefaultAd"));
  assert.ok(page.includes("!actionAd && !onlyDefaultAd"));
  const dropped = relevantPlan(offerPlanForArticle({ ...base, title: "宇宙望遠鏡の新しい観測", genreSlug: "business" }, [], []));
  assert.equal(dropped.offer, undefined);
  assert.equal(dropped.rail, undefined);
  assert.equal(dropped.inline, undefined);
  assert.equal(dropped.droppedDefault, true);
});
