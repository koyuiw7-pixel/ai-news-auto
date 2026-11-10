// 話題 → サイト内のお金のページの表（lib/money-pages.ts。2026-11-10 M2）と、要点の下の「自分は対象か確かめる」の1行。
// Next.js を起動せずに、実際の記事・ガイド・ツールのページで検査する。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const loadTs = (rel, mocks = {}) => {
  const file = path.join(root, rel);
  const out = ts.transpileModule(read(rel), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  const original = mod.require.bind(mod);
  mod.require = (name) => (name in mocks ? mocks[name] : original(name));
  mod._compile(out, file);
  return mod.exports;
};
const money = loadTs("lib/money-pages.ts");
const article = (slug) => JSON.parse(read(`content/articles/${slug}.json`));
const linkFor = (slug) => money.moneyLinkFor(article(slug))?.href;

test("記事 → 「自分は対象か確かめる」の行き先（実際の記事）", () => {
  assert.equal(linkFor("pension-support-benefit-old-age-eligibility"), "/articles/pension-support-benefit-old-age-check");
  assert.equal(linkFor("kyoukai-kenpo-childbirth-allowance"), "/articles/childbirth-allowance-eligibility-check");
  assert.equal(linkFor("child-allowance-third-child-monthly-30000"), "/articles/child-allowance-eligibility-check");
  assert.equal(linkFor("kogaku-ryoyohi-2026-tasukai-kaisu"), "/guides/kogaku-ryoyohi");
});

test("自分自身へはリンクしない（次の行き先か、無ければ何も出さない）", () => {
  assert.equal(linkFor("child-allowance-eligibility-check"), "/guides/jidou-teate");
  assert.equal(linkFor("pension-support-benefit-old-age-check"), undefined);
  assert.equal(linkFor("childbirth-allowance-eligibility-check"), undefined);
});

test("お金の話題でない記事（AI のニュース）には出さない", () => {
  const ai = fs
    .readdirSync(path.join(root, "content/articles"))
    .filter((f) => f.endsWith(".json"))
    .map((f) => { try { return JSON.parse(read(`content/articles/${f}`)); } catch { return null; } })
    .filter((a) => a && a.genreSlug === "ai")
    .slice(0, 50);
  assert.ok(ai.length > 0);
  for (const a of ai) assert.equal(money.moneyLinkFor(a), undefined, a.slug);
  assert.equal(money.moneyLinkFor({ slug: "x", title: "OpenAIが新しいモデルを発表", tags: ["ChatGPT"] }), undefined);
});

test("表の行き先・ガイド・記事は、どれも実在するページ", () => {
  const exists = (href) => {
    const [, section, slug] = href.split("/");
    if (section === "articles") return fs.existsSync(path.join(root, "content/articles", `${slug}.json`));
    if (section === "guides") return fs.existsSync(path.join(root, "content/howto", `${slug}.json`));
    if (section === "tools") return fs.existsSync(path.join(root, "app/tools", slug, "page.tsx"));
    return false;
  };
  for (const row of money.MONEY_PAGES) {
    assert.ok(exists(row.href), row.href);
    if (row.second) assert.ok(exists(row.second.href), row.second.href);
    if (row.guide) assert.ok(exists(`/guides/${row.guide}`), row.guide);
    for (const g of row.guides ?? []) assert.ok(exists(`/guides/${g}`), g);
    for (const a of row.articles ?? []) assert.ok(exists(`/articles/${a}`), a);
  }
});

test("見える言葉に「｜」「ざっくり」を使わない", () => {
  const texts = money.MONEY_PAGES.flatMap((row) => [row.label, row.second?.label ?? ""]);
  texts.push(read("components/MoneyCheckLink.tsx"));
  const tool = read("components/calc/ToolPage.tsx");
  texts.push(tool.slice(tool.indexOf("function ToolRelated")));
  for (const t of texts) {
    assert.ok(!t.includes("｜"), t);
    assert.ok(!t.includes("ざっくり"), t);
  }
});

test("1行の部品: data-money-link の付いた内部リンク1つだけ（PR の印は付けない）", () => {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const Link = ({ href, children, ...rest }) => React.createElement("a", { ...rest, href }, children);
  const { default: MoneyCheckLink } = loadTs("components/MoneyCheckLink.tsx", { "next/link": { __esModule: true, default: Link } });
  const html = renderToStaticMarkup(React.createElement(MoneyCheckLink, { target: money.moneyLinkFor(article("pension-support-benefit-old-age-eligibility")) }));
  assert.match(html, /data-money-link="" [^>]*href="\/articles\/pension-support-benefit-old-age-check"/);
  assert.equal((html.match(/<a /g) ?? []).length, 1);
  assert.ok(html.includes("自分は対象か確かめる → 年金生活者支援給付金の対象を確かめる"));
  assert.ok(!/data-aff-pos|sponsored/.test(html));
  assert.equal(renderToStaticMarkup(React.createElement(MoneyCheckLink, { target: undefined })), "");
});

test("今までの見た目: 要点の一覧のすぐ後ろ、シェアと最初の広告の枠より前。広告の枠の数と順は変えない", () => {
  const page = read("app/articles/[slug]/page.tsx");
  const classic = page.slice(page.indexOf('return (\n    <div className="mx-auto max-w-[1240px]'));
  const points = classic.indexOf('id="points-heading"');
  const link = classic.indexOf("<MoneyCheckLink target={moneyLink}");
  const share = classic.indexOf("<ShareButtons");
  const firstAd = classic.search(/<AdSlot|<RailRanking|<ActionAd|<CtaBanner|<ShopLinks|<CompareOffers/);
  assert.ok(points > 0 && points < link && link < share && share < firstAd, `${points} ${link} ${share} ${firstAd}`);
  // 1つの記事に1回だけ
  assert.equal((page.match(/<MoneyCheckLink /g) ?? []).length, 1);
  // 広告の枠の並びは、この1行が無いときと同じ（1行を除いた本文と、広告の部品の順が一致する）
  const ads = (src) => src.match(/<(AdSlot|RailRanking|ActionAd|CtaBanner|ShopLinks|CompareOffers) [^>]*/g);
  assert.deepEqual(ads(classic), ads(classic.replace(/<MoneyCheckLink [^>]*\/>/, "")));
});

test("ノワール: 要点の箱のすぐ下（「すぐにできること」と1つ目の PR より前）。PR の組み立てには入れない", () => {
  const layout = read("components/noir/NoirArticle.tsx");
  const sum = layout.indexOf('className="nr-sum"');
  const quick = layout.indexOf("{slots.quick}");
  const early = layout.indexOf("{slots.adEarly");
  assert.ok(sum > 0 && sum < quick && quick < early);
  const noir = read("components/noir/noirArticlePage.tsx");
  const quickSlot = noir.slice(noir.indexOf("quick:"), noir.indexOf("story:"));
  assert.ok(quickSlot.indexOf("<MoneyCheckLink target={moneyLink}") < quickSlot.indexOf("<QuickActions"));
  assert.equal((noir.match(/<MoneyCheckLink /g) ?? []).length, 1);
  // 本文の列の PR（adBlocks）は今までどおり。この1行は PR の数に数えない
  const adBlocks = noir.slice(noir.indexOf("const adBlocks"), noir.indexOf("const [adEarly, adMidPr, adEnd]"));
  assert.ok(adBlocks.length > 0 && !adBlocks.includes("moneyLink"));
  // 記事ページから同じ値を渡す
  assert.match(read("app/articles/[slug]/page.tsx"), /const moneyLink = moneyLinkFor\(article\);/);
});

test("読まれ方の記録: この1行を押したら「money」として数える（保存の形は同じ）", () => {
  assert.match(read("components/ReadingBeacon.tsx"), /link\.closest\("\[data-money-link\]"\) \? "money"/);
  assert.match(read("lib/reading.ts"), /EXIT_ZONES = \[[^\]]*"money"/);
  assert.match(read("scripts/reading_report.py"), /"money": "要点の下の「自分は対象か確かめる」"/);
});

test("[A12] ノワールの記事にも「この一覧に載っています」（値上げの記事 → /roundups/price-hikes）", () => {
  const noir = read("components/noir/noirArticlePage.tsx");
  assert.match(noir, /<TopicListMembership slug=\{article\.slug\}/);
  const lists = JSON.parse(read("content/topic_lists.json")).lists;
  const priceNoir = (lists["price-hikes"] ?? []).map((e) => e.slug).find((slug) => {
    try { return article(slug).layout === "noir"; } catch { return false; }
  });
  assert.ok(priceNoir, "値上げの一覧に載っているノワールの記事がある");
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const Link = ({ href, children, ...rest }) => React.createElement("a", { ...rest, href }, children);
  const topicLists = loadTs("lib/topic-lists.ts", {
    "@/content/topic_lists.json": JSON.parse(read("content/topic_lists.json")),
    "@/lib/articles": { getArticleSummary: () => undefined },
    "@/lib/companies": { companyOf: () => ({ slug: "other" }), OTHER: { slug: "other" } },
    "@/lib/headline": { displayHeadline: (t) => t, gateHeadline: (t) => t },
  });
  const { default: Membership } = loadTs("components/TopicListMembership.tsx", { "next/link": { __esModule: true, default: Link }, "@/lib/topic-lists": topicLists });
  const html = renderToStaticMarkup(React.createElement(Membership, { slug: priceNoir }));
  assert.match(html, /href="\/roundups\/price-hikes"/);
});

test("[A12] 計算ツールのページ → 同じ話題の記事とガイド（防衛特別所得税は本文で扱う記事も）", () => {
  const all = fs
    .readdirSync(path.join(root, "content/articles"))
    .filter((f) => f.endsWith(".json"))
    .map((f) => { try { return JSON.parse(read(`content/articles/${f}`)); } catch { return null; } })
    .filter(Boolean)
    .sort((a, b) => String(b.publishedAt).localeCompare(String(a.publishedAt)));
  const defense = money.toolRelatedArticleSlugs("/tools/defense-tax", all);
  assert.ok(defense.length >= 1, "防衛特別所得税の計算から記事へ");
  for (const slug of defense) assert.ok(read(`content/articles/${slug}.json`).includes("防衛特別所得税"), slug);
  assert.ok(money.moneyRowsForTool("/tools/defense-tax").some((row) => (row.guides ?? []).length > 0));
  const furusato = money.toolRelatedArticleSlugs("/tools/furusato-limit", all);
  assert.ok(furusato.length >= 1);
  for (const slug of furusato) assert.match(`${article(slug).title} ${(article(slug).tags ?? []).join(" ")}`, /ふるさと納税|ワンストップ特例/);
  // 記事からツールへは calculatorForArticle（行き来できる）
  const calc = loadTs("lib/calculators.ts");
  assert.equal(calc.calculatorForArticle(article(furusato[0])).kind, "furusato-limit");
  assert.match(read("components/calc/ToolPage.tsx"), /<ToolRelated href=\{meta\.href\} \/>/);
});
