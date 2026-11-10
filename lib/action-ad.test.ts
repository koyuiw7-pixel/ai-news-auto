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
  assert.ok(plan.rail, "記事末（PC は右側）の枠がある");
  const shown = [...keysOf(ad!.items.map((x) => x.item)), ...keysOf(plan.inline?.items.slice(0, 3)), ...keysOf(plan.rail!.items.slice(0, 3))];
  assert.equal(new Set(shown).size, shown.length, `同じ商品を2回出さない: ${shown}`);
  // 2026-11-10 チームの点検（Grok）: 流出の記事で、流出への対策のすぐ後に格安SIMが出ていた（話題がずれると押されない）。
  // 流出の記事はセキュリティの商品だけ。合う商品が足りない枠は出さない（ずれた広告で埋めない）
  const allowed = /^(norton|virusbuster|eset|surfshark)$/;
  for (const key of shown) assert.match(key, allowed);
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
  // 実際のページと同じ渡し方（行動欄の商品は除き、場面の一番手だけ右側・記事末の先頭に置く）でも、右側の先頭は電源
  const page = offerPlanForArticle(outage, real.items.map((x) => x.item.key), [real.items[0].item.key]);
  assert.equal(page.rail!.items[0].key, real.items[0].item.key);
  assert.ok(!page.inline || !page.inline.items.some((i) => i.key === real.items[0].item.key), "本文中の枠には重ねない");
  for (const { pixel } of real.items) if (pixel) assert.ok(!page.rail!.pixels.includes(pixel), "表示の計測は行動欄で数える");
  assert.ok(real.lead && real.lead.length <= 36, "つなぎの一文はスマホで2行まで");
});

// 2026-11-10 M1: エネピは A8 の成果条件を確かめきれていないので先頭にしない。切り替え先（エルピオでんき）を先に
test("電気代の記事は、エルピオでんきが先、エネピは2番目", () => {
  const ad = actionAdForArticle(article("t-bill", "電気代、12月使用分から補助終了で値上がり", ["電気料金"]))!;
  assert.deepEqual(ad.items.map((x) => x.item.key), ["elpio", "enepi"]);
  const heater = actionAdForArticle(fromFile("heater-power-cost-per-hour"))!;
  assert.equal(heater.items[0].item.key, "elpio");
  assert.ok(!heater.items.some((x) => x.item.key === "tainavi"), "太陽光の話でない記事にタイナビを出さない");
  const plan = offerPlanForArticle(fromFile("heater-power-cost-per-hour"), heater.items.map((x) => x.item.key));
  for (const box of [plan.rail, plan.inline, plan.offer]) assert.ok(!box || !box.items.some((i) => i.key === "tainavi"));
});

test("太陽光・蓄電池の見出しの記事だけにタイナビ", () => {
  const ad = actionAdForArticle(article("t-solar", "家庭用の蓄電池、設置の補助金が来年度も継続", ["蓄電池", "補助金"]))!;
  assert.equal(ad.key, "solar");
  assert.ok(ad.items.some((x) => x.item.key === "tainavi"));
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
