const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

// 2026-11-10 オーナー「画像またでてない記事あるよ」「画像が見切れている記事があるのはダサい」「ホームは玄関」。
// 一覧・トップの写真（lib/article-index.mjs の photoOf）と、トップの主役の決まり（lib/home-lead.ts）を確かめる
const root = path.resolve(__dirname, "..");
const own = (name) => `https://ai-tech-express.jp/img/${name}.jpg`;

test("写真の無い記事・文字のカード・ロゴは写真なし。表紙用の AI のイメージがあればそれを「AI生成」で使う", async () => {
  const { photoOf } = await import(path.join(root, "lib/article-index.mjs"));
  assert.equal(photoOf({ slug: "a", thumbnail: "" }), undefined);
  assert.equal(photoOf({ slug: "a", thumbnail: "", imageCredit: { kind: "card" } }), undefined);
  assert.equal(photoOf({ slug: "a", thumbnail: own("a-logo"), imageCredit: { kind: "official", imageKind: "logo" } }), undefined);
  const cover = { coverImage: own("a-muse-1"), coverCredit: { kind: "ai", model: "muse" } };
  assert.deepEqual(photoOf({ slug: "a", thumbnail: "", ...cover }), { src: own("a-muse-1"), ai: true });
  assert.deepEqual(photoOf({ slug: "a", thumbnail: own("a-logo"), imageCredit: { kind: "official", imageKind: "logo" }, ...cover }), { src: own("a-muse-1"), ai: true });
  // AI の見出し画像より、見出しとのつながりを確かめた表紙用の AI のイメージを先に
  assert.equal(photoOf({ slug: "a", thumbnail: own("a-ai"), imageCredit: { kind: "ai" }, ...cover }).src, own("a-muse-1"));
  // 地震・津波の記事は写真なし
  assert.equal(photoOf({ slug: "a", thumbnail: "", noPhoto: true, ...cover }), undefined);
  // ほかの記事のために保存した画像は使わない
  assert.equal(photoOf({ slug: "a", thumbnail: own("other-photo"), imageCredit: { kind: "stock" } }), undefined);
});

test("公式の写真は主役の位置で切り抜き、文字の多いバナーは切り抜かない", async () => {
  const { photoOf } = await import(path.join(root, "lib/article-index.mjs"));
  const src = own("a-photo");
  const p = photoOf({ slug: "a", thumbnail: src, imageCredit: { kind: "official" }, imageFocus: { x: 0.3, y: 0.7, box: [0, 0, 1, 1], ar: 1.9, src } });
  assert.equal(p.pos, "30% 70%");
  assert.equal(p.ar, 1.9);
  assert.equal(photoOf({ slug: "a", thumbnail: src, imageCredit: { kind: "official", imageKind: "banner" } }).fit, "contain");
});

test("トップの主役は暮らしとお金の記事・写真のある記事から選ぶ（AI の企業向けの話・写真の無い記事を主役にしない）", () => {
  const src = fs.readFileSync(path.join(root, "lib/home-lead.ts"), "utf8");
  assert.match(src, /LIFE_MONEY_GENRES\.has\(a\.genreSlug\)/);
  assert.match(src, /Boolean\(a\.photo\)/);
  assert.match(src, /!containPhoto\(a\.photo\)/);
  const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
  assert.match(page, /pickHomeLead\(/);
  // 暮らしとお金の列は AI の新着より上
  assert.ok(page.indexOf("<NewsHub") < page.indexOf("latest-heading"), "暮らしとお金の列が AI の新着より下にある");
});
