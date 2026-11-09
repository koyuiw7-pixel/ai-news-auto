/** トップの「暮らしとお金のニュース」の列の下の PR 枠（home-mid）が、列の記事の話題で選ばれるか（content/offers.json の実データ。通信なし）。 */
import assert from "node:assert/strict";
import fs from "node:fs";
import type { ArticleSummary } from "./articles";
import { HOME_MID_TOPICS, homeSectionOffer, homeSectionTopics } from "./offers";

let passed = 0;
function test(name: string, fn: () => void) { fn(); passed++; console.log(`ok home-offer ${name}`); }
const article = (slug: string, title: string, tags: string[], genreSlug = "public") =>
  ({ slug, title, tags, lede: "", genreSlug, highlights: [] }) as unknown as ArticleSummary;

const leak = [
  article("h-leak1", "ドコモ情報流出、最大約30万件　対象かどうかと今やること", ["通信", "情報流出", "ドコモ"]),
  article("h-leak2", "通販サイトに不正アクセス、カード情報が流出した可能性", ["不正アクセス", "情報流出"]),
];
const power = [
  article("h-power1", "電気代、12月使用分から補助終了で値上がり", ["電気料金"], "lifestyle"),
  article("h-power2", "電気料金の値上げ、1月から　家庭への影響", ["電気料金", "値上げ"], "lifestyle"),
  article("h-power3", "冬の電気代を抑える、暖房の使い方", ["電気代", "節約"], "lifestyle"),
];
const unrelated = article("h-other", "褒章の受章者が決まる", ["表彰"]);

test("流出の記事が多い列はセキュリティ", () => {
  const offer = homeSectionOffer([...leak, unrelated]);
  assert.ok(offer);
  assert.equal(offer.topic, "life-leak");
  for (const item of offer.items) assert.match(item.name, /ノートン|ウイルスバスター|ESET/);
});

test("電気・暖房の記事が多い列は電気の見直し", () => {
  const offer = homeSectionOffer([...leak, ...power]);
  assert.ok(offer);
  assert.equal(homeSectionTopics([...leak, ...power])[0].key, "life-energy");
  assert.equal(offer.topic, "life-energy");
  for (const item of offer.items) assert.match(item.name, /エルピオ|エネピ|タイナビ/);
});

test("合う話題が無い列は、いちばん幅広い固定費の見直し", () => {
  const offer = homeSectionOffer([unrelated]);
  assert.ok(offer);
  assert.equal(offer.topic, "life-household");
  assert.equal(offer.fallback, true);
});

test("上の枠に出た商品は出さない（同じ話題の商品が残らなければ次の話題）", () => {
  const top = homeSectionOffer(leak);
  assert.ok(top);
  const keys = top.items.map((i) => i.key);
  const mid = homeSectionOffer(leak, keys);
  assert.ok(mid);
  for (const item of mid.items) assert.ok(!keys.includes(item.key), `${item.key} が2つの枠に出ている`);
});

test("上の枠と同じ話題は後回し（主役も列も流出なら、列で次に多い話題）", () => {
  const offer = homeSectionOffer([...leak, ...leak.map((a) => ({ ...a, slug: `${a.slug}-b` })), power[0]], [], ["security"]);
  assert.ok(offer);
  assert.equal(offer.topic, "life-energy");
  // 列にほかの話題が無ければ、同じ話題の残りの商品
  const only = homeSectionOffer(leak, ["virusbuster"], ["security"]);
  assert.ok(only);
  assert.equal(only.topic, "life-leak");
  assert.ok(only.items.every((i) => i.key !== "virusbuster"));
});

test("最大3つ・提携リンクだけ・販売期限のある商品は入れない・表示の計測は並ぶ商品の分だけ", () => {
  const offer = homeSectionOffer(power);
  assert.ok(offer && offer.items.length >= 1 && offer.items.length <= 3);
  for (const item of offer.items) {
    assert.match(item.url, /^https:\/\/px\.a8\.net\/svt\/ejp\?a8mat=/);
    assert.equal(item.activeUntil, undefined);
  }
  assert.ok(offer.pixels.length <= offer.items.length);
});

test("選んでよい話題は暮らしとお金だけ（投資・カード・借入・健康食品・化粧品の話題を入れない）", () => {
  const offers = JSON.parse(fs.readFileSync("content/offers.json", "utf8"));
  const keys = new Set(offers.topics.map((t: { key: string }) => t.key));
  for (const [key, canonical] of Object.entries(HOME_MID_TOPICS)) {
    assert.ok(keys.has(key), `${key} が offers.json に無い`);
    assert.ok(keys.has(canonical), `${canonical} が offers.json に無い`);
    assert.doesNotMatch(key, /invest|payment|loan|card|kids|travel/);
  }
  for (const key of new Set(Object.values(HOME_MID_TOPICS))) {
    const topic = offers.topics.find((t: { key: string }) => t.key === key);
    for (const partner of topic.partners) {
      const p = offers.partners[partner];
      assert.doesNotMatch(`${p?.name ?? ""} ${p?.label ?? ""}`, /化粧|コスメ|サプリ|健康食品|カジノ|競馬|FX|暗号資産|ローン|キャッシング|借入/);
    }
  }
});

console.log(`home-offer: ${passed} passed`);
