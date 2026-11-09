/** ニュース → 比較記事の導線（lib/comparison.ts）と、その表示（components/FunnelCard・CompareOffers）。content/offers.json の実データ。通信なし */
import assert from "node:assert/strict";
import fs from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { ArticleSummary } from "./articles";
import { COMPARE_SLOT, compareOffersFor, comparisonByTopic, comparisonTopicOf, funnelForArticle, insertCompareSlot, isComparison } from "./comparison";
import FunnelCard from "../components/FunnelCard";
import CompareOffers from "../components/CompareOffers";
import ArticleProse from "../components/ArticleProse";
import { summarize } from "./article-index.mjs";
import { actionAdRules } from "./offers";

let passed = 0;
function test(name: string, fn: () => void) { fn(); passed++; console.log(`ok comparison ${name}`); }
const fromFile = (slug: string) => JSON.parse(fs.readFileSync(`content/articles/${slug}.json`, "utf8")) as ArticleSummary;
const NOW = Date.parse("2026-11-09T12:00:00+09:00");

const comparison = (slug: string, title: string, topic?: string, extra: Partial<ArticleSummary> = {}) =>
  ({
    slug, title, kind: "comparison", comparisonTopic: topic, tags: [], keywords: [], highlights: [], lede: "", description: "",
    genreSlug: "lifestyle", genre: "暮らし", publishedAt: "2026-11-09T03:00:00Z", thumbnail: `https://ai-tech-express.jp/img/${slug}.jpg`,
    imageCredit: { kind: "ai" }, ...extra,
  }) as unknown as ArticleSummary;

const fixtures = [
  comparison("security-software-compare", "情報流出が不安な人へ セキュリティソフト3製品を価格と台数で比べた", "leak"),
  comparison("disaster-prep-compare", "防災の備えの選び方 ポータブル電源と非常食、セットの中身と価格を比べる", "disaster"),
  comparison("power-plan-compare", "電気代の見直しは単価だけでは決まらない、東京エリア4プランの基本料金と従量単価", "energy"),
];

test("比較記事の話題（題名から。scripts/muse_articles.py の comparison_topic と同じ答え）", () => {
  const cases: [string, string][] = [
    ["ふるさと納税の申込先、2025年10月にポイント付与が終わり選び方は手続きで比べる時代に", "furusato"],
    ["12月に料金が変わるahamoとソフトバンク光、スマホと光回線の月額を公式料金で比較", "mobile"],
    ["情報流出が不安な人へ セキュリティソフト3製品を価格と台数で比べた", "leak"],
    ["防災の備えの選び方 ポータブル電源と非常食、セットの中身と価格を比べる", "disaster"],
    ["電気代の見直しは単価だけでは決まらない、東京エリア4プランの基本料金と従量単価", "energy"],
  ];
  for (const [title, key] of cases) assert.equal(comparisonTopicOf({ title, lede: "", description: "" }), key, title);
  // 公開時に決めた話題があればそれを使う
  assert.equal(comparisonTopicOf({ title: "防災の備え", lede: "", description: "", comparisonTopic: "leak" }), "leak");
});

test("印の無い Muse の「比較」の原稿もファイル名で比較記事と分かる", () => {
  assert.ok(isComparison({ museFile: "20261109-比較-電気代の見直し方.md" }));
  assert.ok(!isComparison({ museFile: "20261108-速報解説-ドコモ流出の対象確認.md" }));
  assert.ok(!isComparison({}));
});

test("ドコモの情報流出の記事 → セキュリティソフトの比較（判断ガイドの直後と記事の終わり）", () => {
  const docomo = fromFile("docomo-online-shop-data-leak");
  const card = funnelForArticle(docomo, [...fixtures, docomo], undefined, NOW);
  assert.ok(card);
  assert.equal(card.topic, "leak");
  assert.equal(card.target.slug, "security-software-compare");
  assert.equal(card.placement, "both");
  assert.match(card.reason, /詐欺|不正ログイン/);
});

test("静岡の地震と地震保険の記事 → 防災の備えの比較（火災保険の比較が無いので近い話題へ）", () => {
  const quake = fromFile("shizuoka-west-quake-aftershock-insurance");
  const card = funnelForArticle(quake, fixtures, undefined, NOW);
  assert.ok(card);
  assert.equal(card.topic, "disaster");
  assert.equal(card.target.slug, "disaster-prep-compare");
});

test("比較記事が無い話題・関係の無い記事・比較記事そのものには出さない", () => {
  const docomo = fromFile("docomo-online-shop-data-leak");
  assert.equal(funnelForArticle(docomo, fixtures.slice(1), undefined, NOW), undefined);
  const ai = { ...docomo, slug: "t-ai", title: "OpenAI、新しい画像生成モデルを公開", seoTitle: "", tags: ["OpenAI"], keywords: [], lede: "", description: "", highlights: [] } as ArticleSummary;
  assert.equal(funnelForArticle(ai, fixtures, undefined, NOW), undefined);
  assert.equal(funnelForArticle(fixtures[0], fixtures, undefined, NOW), undefined);
});

test("地震・津波の速報と、速報の当日は記事の終わりだけ", () => {
  const base = fromFile("shizuoka-west-quake-aftershock-insurance");
  const jma = { ...base, slug: "quake-20261109-1200", channelSlug: "jma" } as ArticleSummary;
  assert.equal(funnelForArticle(jma, fixtures, undefined, NOW)?.placement, "end");
  const fresh = { ...base, slug: "t-fresh", breaking: true, publishedAt: "2026-11-09T02:00:00Z" } as ArticleSummary;
  assert.equal(funnelForArticle(fresh, fixtures, undefined, NOW)?.placement, "end");
});

test("重複・検索に出さない比較記事は受け皿にしない。同じ話題は新しい方", () => {
  const map = comparisonByTopic([
    comparison("leak-new", "セキュリティソフトの選び方 情報流出が心配な人へ", "leak"),
    comparison("leak-old", "情報流出に備えるソフトの比較", "leak"),
    comparison("energy-hidden", "電気代の比べ方", "energy", { indexable: false }),
  ]);
  assert.equal(map.get("leak")?.slug, "leak-new");
  assert.equal(map.has("energy"), false);
});

test("比較記事の提携先: 話題の partners の順・A8 のリンクだけ", () => {
  const offers = compareOffersFor({ ...fixtures[0], body: "" });
  assert.ok(offers);
  assert.equal(offers.topic, "leak");
  assert.ok(offers.items.length >= 2);
  for (const { item } of offers.items) {
    assert.match(item.name, /ノートン|ウイルスバスター|ESET/);
    assert.match(item.url, /^https:\/\/px\.a8\.net\/svt\/ejp\?a8mat=/);
  }
  assert.equal(compareOffersFor({ ...fromFile("docomo-online-shop-data-leak"), body: "" }), undefined, "ニュース記事には出さない");
});

test("比較表の直後に印を入れ、本文がそこで分かれて一覧が挟まる", () => {
  const html = "<p>前</p><table><tr><td>a</td></tr></table><p>後</p><table><tr><td>b</td></tr></table>";
  const marked = insertCompareSlot(html);
  assert.equal(marked.split(COMPARE_SLOT).length, 2);
  assert.ok(marked.indexOf(COMPARE_SLOT) < marked.indexOf("<p>後</p>"));
  assert.equal(insertCompareSlot("<p>表なし</p>"), "<p>表なし</p>");
  const out = renderToStaticMarkup(createElement(ArticleProse, { html: marked, className: "prose", compareSlot: createElement("aside", { id: "slot" }) }));
  assert.ok(out.indexOf('id="slot"') > out.indexOf("</table>") && out.indexOf('id="slot"') < out.indexOf("後"));
  assert.ok(!out.includes(COMPARE_SLOT));
  // 一覧を渡さないときは印を消す
  assert.ok(!renderToStaticMarkup(createElement(ArticleProse, { html: marked, className: "prose" })).includes(COMPARE_SLOT));
});

test("提携先の一覧の表示: PR の札・sponsored nofollow・公式サイトで見る", () => {
  const offers = compareOffersFor({ ...fixtures[0], body: "" })!;
  const out = renderToStaticMarkup(createElement(CompareOffers, { offers, pos: "compare-table" }));
  assert.match(out, /data-aff-pos="compare-table"/);
  assert.match(out, />PR</);
  assert.equal((out.match(/rel="sponsored nofollow[^"]*"/g) ?? []).length, offers.items.length);
  assert.equal((out.match(/公式サイトで見る/g) ?? []).length, offers.items.length);
  assert.match(out, /href="https:\/\/px\.a8\.net\/svt\/ejp\?a8mat=/);
});

test("「次に読む」のカードの表示: 題名・理由・画像・内部リンク（PR の札は付けない）", () => {
  const card = funnelForArticle(fromFile("docomo-online-shop-data-leak"), fixtures, undefined, NOW)!;
  const out = renderToStaticMarkup(createElement(FunnelCard, { card, pos: "mid" }));
  assert.match(out, /次に読む：情報流出が不安な人へ/);
  assert.match(out, /href="\/articles\/security-software-compare"/);
  assert.match(out, /data-compare-funnel="leak"/);
  assert.match(out, /security-software-compare\.jpg/);
  assert.ok(!/sponsored|>PR</.test(out));
});

test("本番の不具合（2026-11-09 15:31）: 印も話題の語も題名に無い防災の比較記事を、索引が本文から防災と決め、地震の記事にカードが出る", () => {
  const raw = JSON.parse(fs.readFileSync("content/articles/portable-power-emergency-food-compare.json", "utf8"));
  // 公開時の印が無かった状態（古い仕組みで公開された）を再現する
  delete raw.kind;
  delete raw.comparisonTopic;
  const summary = summarize(raw, actionAdRules()) as unknown as ArticleSummary;
  assert.equal(summary.kind, "comparison");
  assert.equal(summary.comparisonTopic, "disaster");
  const quake = fromFile("shizuoka-west-quake-aftershock-insurance");
  const card = funnelForArticle(quake, [summary, quake], undefined, NOW);
  assert.ok(card, "地震の記事にカードが出ない");
  assert.equal(card.target.slug, "portable-power-emergency-food-compare");
  // ニュース記事の索引には比較の印を付けない
  assert.equal((summarize(JSON.parse(fs.readFileSync("content/articles/shizuoka-west-quake-aftershock-insurance.json", "utf8")), actionAdRules()) as { kind?: string }).kind, undefined);
});

test("表の無い比較記事は、最初の章の終わり（2つ目の h2 の前）に一覧の印", () => {
  const html = "<p>導入</p><h2>容量</h2><p>a</p><h2>非常食</h2><p>b</p>";
  const marked = insertCompareSlot(html);
  assert.equal(marked, `<p>導入</p><h2>容量</h2><p>a</p>${COMPARE_SLOT}<h2>非常食</h2><p>b</p>`);
  assert.equal(insertCompareSlot("<h2>1つだけ</h2><p>a</p>"), "<h2>1つだけ</h2><p>a</p>");
});

console.log(`comparison: ${passed} passed`);
