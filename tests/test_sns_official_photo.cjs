const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// SNS のカードに敷く公式の写真（lib/sns-photo.ts）。2026-11-07 オーナー承認（台帳 S45）: 公式発表の写真を出典つきで使う。
// Python 側（scripts/sns_rules.py の sns_photo）は tests/test_sns_official_photo_20261107.py が同じ例で確かめる。
const root = path.resolve(__dirname, "..");
function load(rel) {
  const file = path.join(root, rel);
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true },
  }).outputText;
  const m = new Module(file, module);
  m.filename = file;
  m.paths = Module._nodeModulePaths(path.dirname(file));
  m._compile(compiled, file);
  return m.exports;
}
const { snsPhoto, snsCardArticle } = load("lib/sns-photo.ts");
const { officialCreditText } = load("lib/image-credit.ts");

const IMG = "https://ai-tech-express.jp/img/";
const OFFICIAL = {
  slug: "samsung-buds-x", thumbnail: `${IMG}samsung-buds-x-1a2b3c4d.jpg`, channelSlug: "samsung", sourceUrl: "https://news.samsung.com/global/x",
  imageCredit: { kind: "official", org: "Samsung", sourceUrl: "https://news.samsung.com/global/x", width: 1200, height: 675 },
};
const AI_WITH_BODY = {
  slug: "nvidia-muse-x", thumbnail: `${IMG}nvidia-muse-x-aaaa1111.jpg`, channelSlug: "nvidia", sourceUrl: "https://blogs.nvidia.com/blog/x/",
  imageCredit: { kind: "ai", model: "flux-2-klein-4b", provider: "Cloudflare Workers AI" },
  imageFocus: { x: 0.5, y: 0.5, box: [0.2, 0.2, 0.8, 0.8], ar: 1.9, src: `${IMG}nvidia-muse-x-aaaa1111.jpg` },
  bodyImages: [
    { src: `${IMG}nvidia-muse-x-fig1-bbbb2222.jpg`, width: 1200, height: 628, kind: "dense", credit: "NVIDIA", sourceUrl: "https://blogs.nvidia.com/blog/x/" },
    { src: `${IMG}nvidia-muse-x-fig2-cccc3333.jpg`, width: 700, height: 393, kind: "photo", credit: "NVIDIA", sourceUrl: "https://blogs.nvidia.com/blog/x/" },
  ],
};
const AI_ONLY = {
  slug: "yokohama-tire-recall-x", thumbnail: `${IMG}yokohama-tire-recall-x-dddd4444.jpg`, channelSlug: "mlit",
  imageCredit: { kind: "ai", model: "flux-2-klein-4b" },
  bodyImages: [{ src: `${IMG}yokohama-tire-recall-x-fig1-eeee5555.jpg`, kind: "dense", credit: "国土交通省" }],
};
const RESEARCH = {
  slug: "tsr-bankruptcy-x", thumbnail: `${IMG}tsr-bankruptcy-x-ffff6666.jpg`, channelSlug: "tsr", sourceUrl: "https://www.tsr-net.co.jp/data/detail/1234_1527.html",
  imageCredit: { kind: "official", org: "東京商工リサーチ", sourceUrl: "https://www.tsr-net.co.jp/data/detail/1234_1527.html" },
  bodyImages: [{ src: `${IMG}tsr-bankruptcy-x-fig1-9999aaaa.jpg`, kind: "photo", credit: "東京商工リサーチ", sourceUrl: "https://www.tsr-net.co.jp/x" }],
};

test("記事の写真が公式の写真ならそのまま使い、出典を出す", () => {
  const photo = snsPhoto(OFFICIAL);
  assert.equal(photo.from, "thumbnail");
  assert.equal(snsCardArticle(OFFICIAL), OFFICIAL);
  assert.equal(officialCreditText(photo.credit), "画像：Samsung（公式発表より）");
});

test("記事の写真が AI でも、本文に公式の写真があればカードはそれ（出典は会社。AI の注記は付かない）", () => {
  const card = snsCardArticle(AI_WITH_BODY);
  assert.equal(card.thumbnail, `${IMG}nvidia-muse-x-fig2-cccc3333.jpg`);
  assert.equal(card.imageCredit.kind, "official");
  assert.equal(officialCreditText(card.imageCredit), "画像：NVIDIA（公式発表より）");
  assert.deepEqual(card.imageFocus.box, [0, 0, 1, 1]);
  assert.equal(card.imageFocus.src, card.thumbnail);
  assert.equal(AI_WITH_BODY.imageCredit.kind, "ai"); // 元の記事は書き換えない
});

test("調査会社・情報会社の画像は使わない（台帳 A37）", () => {
  assert.equal(snsPhoto(RESEARCH), null);
  assert.equal(snsPhoto({ ...OFFICIAL, imageCredit: { ...OFFICIAL.imageCredit, sourceUrl: "https://www.tdb.co.jp/report/x/" } }), null);
  assert.equal(snsPhoto({ ...AI_WITH_BODY, bodyImages: [{ ...AI_WITH_BODY.bodyImages[1], sourceUrl: "https://www.tsr-net.co.jp/x" }] }), null);
});

test("文字が主役の公式の画像（バナー・図・ロゴ・heroOk: false）は使わない", () => {
  for (const imageKind of ["banner", "dense", "logo", "generic"]) {
    assert.equal(snsPhoto({ ...OFFICIAL, imageCredit: { ...OFFICIAL.imageCredit, imageKind } }), null, imageKind);
  }
  assert.equal(snsPhoto({ ...OFFICIAL, heroOk: false }), null);
  const banner = { ...OFFICIAL, imageCredit: { ...OFFICIAL.imageCredit, imageKind: "banner" }, bodyImages: AI_WITH_BODY.bodyImages };
  assert.equal(snsPhoto(banner).from, "body");
});

test("公式の写真が無ければ今までのカード（AI の出典のまま＝「画像はイメージ（AI生成）」）", () => {
  assert.equal(snsPhoto(AI_ONLY), null);
  const card = snsCardArticle(AI_ONLY);
  assert.equal(card, AI_ONLY);
  assert.equal(card.imageCredit.kind, "ai");
  assert.equal(officialCreditText(card.imageCredit), null);
});

test("カードの注記は lib/card-designs.tsx の cardCredit が出典から作る（AI なら AI生成・公式なら officialCreditText）", () => {
  const src = fs.readFileSync(path.join(root, "lib/card-designs.tsx"), "utf8");
  // AI の札は lib/image-credit.ts の aiCreditText（公式の画像が無い発表は「公式画像がないためイメージ（AI生成）」。2026-11-07 台帳 I2）
  assert.match(src, /c\?\.kind === "ai"\) return aiCreditText\(c\)/);
  assert.match(src, /c\?\.kind === "official" \|\| c\?\.kind === "figure"\) return officialCreditText\(c\)/);
  const route = fs.readFileSync(path.join(root, "app/card/[slug]/route.tsx"), "utf8");
  assert.match(route, /snsCardArticle\(found\)/);
});
