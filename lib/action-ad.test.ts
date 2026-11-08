/** 「すぐにできること」のそばの PR が、記事の話題どおりに選ばれるか（content/offers.json の実データ。通信なし）。 */
import assert from "node:assert/strict";
import fs from "node:fs";
import type { ArticleSummary } from "./articles";
import { actionAdForArticle, actionAdRuleFor } from "./action-ad";

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

console.log(`action-ad: ${passed} passed`);
