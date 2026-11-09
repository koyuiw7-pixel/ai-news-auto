/** 「すぐにできること」のそばの PR が、記事の話題どおりに選ばれるか（content/offers.json の実データ。通信なし）。 */
import assert from "node:assert/strict";
import fs from "node:fs";
import type { ArticleSummary } from "./articles";
import { actionAdForArticle, actionAdRuleFor } from "./action-ad";
import { offerPlanForArticle } from "./offers";

let passed = 0;
function test(name: string, fn: () => void) { fn(); passed++; console.log(`ok action-ad ${name}`); }
const article = (slug: string, title: string, tags: string[], lede = "") =>
  ({ slug, title, tags, lede, genreSlug: "public", highlights: [] }) as unknown as ArticleSummary;
const fromFile = (slug: string) => JSON.parse(fs.readFileSync(`content/articles/${slug}.json`, "utf8")) as ArticleSummary;

const cases: [ArticleSummary, string, RegExp][] = [
  [article("t-leak", "ドコモ情報流出、最大約30万件　対象かどうかと今やること", ["通信", "情報流出", "ドコモ"]), "leak", /ノートン|ウイルスバスター|ESET/],
  [article("t-quake", "愛知県知多市、土砂災害の警報基準を通常の8割に", ["防災", "地震"]), "disaster", /ポータブル電源|防災|安心米|スツーレ/],
  [article("t-furusato", "ふるさと納税の期限は12月31日　間に合わなければ確定申告", ["ふるさと納税", "確定申告"]), "furusato", /ふるさと/],
  [article("t-tax", "年末調整の書類、今年から変わる点", ["年末調整", "税金"]), "tax", /freee|マネーフォワード|弥生/],
  [article("t-power", "電気代、12月使用分から補助終了で値上がり", ["電気料金"]), "energy", /エルピオでんき|エネピ|タイナビ/],
  [article("t-move", "引っ越しの住所変更、マイナポータルで一括に", ["引っ越し", "手続き"]), "moving", /引越し侍|BIGLOBE光/],
  [article("t-mobile", "楽天モバイルで通信障害、復旧の見通し", ["通信障害"]), "mobile", /BB\.excite|BIGLOBE光/],
  [article("t-fire", "火災保険料、来年度から平均で値上げ", ["火災保険"]), "fire-insurance", /火災保険/],
  [article("t-water", "能登の一部地域で断水続く　給水所の場所", ["断水"]), "water", /ウォーター|frecious/],
  [article("t-trip", "年末年始の連休、旅行の予約は早めに", ["旅行"]), "travel", /じゃらん|一休/],
  [article("t-pay", "PayPayのポイント還元、12月から条件変更", ["キャッシュレス"]), "payment", /エポスカード/],
];

for (const [a, key, name] of cases) {
  test(`${key}: ${a.title.slice(0, 16)}`, () => {
    const ad = actionAdForArticle(a);
    assert.ok(ad, "広告が選ばれない");
    assert.equal(ad.key, key);
    assert.ok(ad.items.length >= 1 && ad.items.length <= 2);
    for (const { item } of ad.items) {
      assert.match(item.name, name);
      assert.match(item.url, /^https:\/\/px\.a8\.net\/svt\/ejp\?a8mat=/);
    }
  });
}

test("関係のない記事には出さない", () => {
  assert.equal(actionAdForArticle(article("t-ai", "OpenAI、新しい画像生成モデルを公開", ["OpenAI", "画像生成"])), undefined);
});

test("右側の枠に出た商品は後ろに回す", () => {
  const a = article("t-leak2", "大手通販で個人情報が流出、フィッシングに注意", ["情報流出"]);
  const first = actionAdForArticle(a)!.items[0].item.key;
  const again = actionAdForArticle(a, [first])!;
  assert.notEqual(again.items[0].item.key, first);
});

test("実際の3記事（ドコモ・知多市・ふるさと納税）", () => {
  assert.equal(actionAdRuleFor(fromFile("docomo-online-shop-data-leak"))?.key, "leak");
  assert.equal(actionAdRuleFor(fromFile("chita-landslide-warning-threshold-lowered"))?.key, "disaster");
  assert.equal(actionAdRuleFor(fromFile("furusato-nozei-deadline-2026"))?.key, "furusato");
});

// 2026-11-09: ドコモの情報流出の記事に、行動欄そばの文字だけの PR と、関係の薄い右側の枠（ココナラなど）しか出ていなかった
const planOf = (a: ArticleSummary) => {
  const ad = actionAdForArticle(a);
  return { ad, plan: offerPlanForArticle(a, (ad?.items ?? []).map((x) => x.item.key)) };
};
const keysOf = (items?: { key: string }[]) => (items ?? []).map((i) => i.key);

test("ドコモの情報流出：行動欄・本文中・記事末の3か所に、流出に合う商品を重ねずに出す", () => {
  const { ad, plan } = planOf(fromFile("docomo-online-shop-data-leak"));
  assert.equal(ad?.key, "leak");
  assert.ok(ad?.reason);
  assert.ok(ad!.items.every(({ item }) => item.image), "バナーの素材がある");
  assert.ok(plan.inline && plan.rail, "本文中と記事末の枠がある");
  const shown = [...keysOf(ad!.items.map((x) => x.item)), ...keysOf(plan.inline!.items.slice(0, 3)), ...keysOf(plan.rail!.items.slice(0, 3))];
  assert.equal(new Set(shown).size, shown.length, `同じ商品を2回出さない: ${shown}`);
  const allowed = /^(norton|virusbuster|eset|surfshark|bb-excite|biglobe-hikari-plus)$/;
  for (const key of shown) assert.match(key, allowed);
  assert.ok(shown.includes("bb-excite") || shown.includes("biglobe-hikari-plus"), "回線の見直しも出す");
  // 行動欄に出した商品の計測は行動欄で数える（右側・本文中の枠のピクセルに入れない）
  for (const { pixel } of ad!.items) if (pixel) assert.ok(!plan.rail!.pixels.includes(pixel));
});

test("地震・防災の記事：防災の商品が本文中と記事末にも出る（ジャンルの既定の会計ソフトにしない）", () => {
  const { ad, plan } = planOf(fromFile("chita-landslide-warning-threshold-lowered"));
  assert.equal(ad?.key, "disaster");
  for (const box of [plan.inline, plan.rail]) {
    assert.ok(box);
    for (const key of keysOf(box!.items)) assert.match(key, /^(jackery|bluetti|akamaru-bousai|alpha-foods|stoole|bang-kasai)$/);
  }
});

test("値上げの記事：家計の固定費の見直し（暮らしの記事だけ。海外の物価統計には出さない）", () => {
  assert.equal(actionAdRuleFor(article("t-price", "不二家の飲料7品、2027年1月出荷分から約7〜14%値上げ", ["値上げ"]))?.key, "household");
  assert.equal(actionAdRuleFor(article("t-euro", "ユーロ圏の物価上昇率4.0%に　エネルギーは20%超", ["物価"])), undefined);
});

test("候補を全部行動欄に出した記事でも、ほかの枠は既定の広告で埋める", () => {
  const a = { ...article("t-fire2", "火災保険料、来年度から平均で値上げ", ["火災保険"]), genreSlug: "lifestyle" } as ArticleSummary;
  const { ad, plan } = planOf(a);
  assert.equal(ad?.key, "fire-insurance");
  assert.ok(plan.rail, "右側・記事末の枠が空にならない");
  assert.ok(!keysOf(plan.rail!.items).includes("bang-kasai"));
});

// 2026-11-09 オーナー「これ売れるのかな？」: 停電の記事の先頭が44点の防災セットだった。記事の場面に合う商品を先に出す
test("停電の記事はポータブル電源が先、地震・備蓄の記事は防災セットが先（記事ごとにずらさない）", () => {
  for (const slug of ["t-out1", "t-out2", "t-out3", "t-out4"]) {
    const ad = actionAdForArticle(article(slug, "停電したらまずブレーカーを確認　復旧までにやること", ["停電", "防災"]))!;
    assert.equal(ad.intent, "outage");
    assert.match(ad.items[0].item.key, /^(jackery|bluetti)$/);
    assert.match(ad.lead ?? "", /充電/);
  }
  const quake = actionAdForArticle(article("t-q1", "地震に備える備蓄、家族3日分の目安", ["地震", "備蓄"]))!;
  assert.equal(quake.intent, "quake");
  assert.equal(quake.items[0].item.key, "akamaru-bousai");
  const outage = fromFile("power-outage-breaker-check-guide");
  const real = actionAdForArticle(outage)!;
  assert.match(real.items[0].item.key, /^(jackery|bluetti)$/);
  // 本文中・記事末の枠でも、停電の記事は電源を先に（行動欄に出た分は除く）
  const plan = offerPlanForArticle(outage, []);
  assert.match(plan.rail!.items[0].key, /^(jackery|bluetti)$/);
});

test("電気代の記事は、まず比べるサービス（エネピ）を先に", () => {
  const ad = actionAdForArticle(article("t-bill", "電気代、12月使用分から補助終了で値上がり", ["電気料金"]))!;
  assert.equal(ad.items[0].item.key, "enepi");
});

test("行動欄の商品には向く人・特徴・ボタンの言葉がある（数字は書かない）", () => {
  for (const [title, tags] of [["ドコモ情報流出、最大約30万件", ["情報流出"]], ["停電したらまずブレーカーを確認", ["停電"]], ["電気代が値上がり", ["電気料金"]]] as const) {
    const ad = actionAdForArticle(article(`t-p-${title.length}`, title, [...tags]))!;
    assert.ok(ad.lead, `${title}: つなぎの一文が無い`);
    for (const { item } of ad.items) {
      assert.ok(item.pitch?.fit && item.pitch?.point && item.pitch?.cta, `${item.key}: pitch が無い`);
      assert.notEqual(item.pitch!.cta, "公式サイトで見る");
    }
  }
});

console.log(`action-ad: ${passed} passed`);
