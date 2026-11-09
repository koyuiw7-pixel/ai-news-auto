const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 共有の画像（og:image の /cover/<slug> と SNS の /card/<slug>）に、記事の写真が無いとき表紙用の AI のイメージ（coverImage）を敷く。
// 2026-11-07 オーナー指摘：不二家の値上げの記事（thumbnail ""・coverImage あり）で、X の画像が青い地に「不二家」だけ、
// リンクカードが暗い地に「不二家 ニュースリリース」だけだった。空の・暗い代わりの画像は禁止（写真は記事とつながるもの・表紙には必ず写真）。
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
const { shareImageArticle, snsCardArticle } = load("lib/sns-photo.ts");
const { aiCreditText, officialCreditText } = load("lib/image-credit.ts");
const { coverPath, COVER_VERSION } = load("lib/cover-path.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

const IMG = "https://ai-tech-express.jp/img/";
const FUJIYA = {
  slug: "fujiya-beverage-price-increase-2027",
  title: "不二家、飲料を値上げ",
  thumbnail: "",
  imageCredit: { kind: "card", category: "price" },
  coverImage: `${IMG}fujiya-beverage-price-increase-2027-cover-d977c5e1.jpg`,
  coverCredit: { kind: "ai", model: "flux-2-klein-4b", provider: "Cloudflare Workers AI", relevant: true },
};

test("記事の写真が空で coverImage があれば、カバーもカードもその写真を「画像はイメージ（AI生成）」つきで敷く", () => {
  for (const a of [shareImageArticle(FUJIYA), shareImageArticle(snsCardArticle(FUJIYA))]) {
    assert.equal(a.thumbnail, FUJIYA.coverImage);
    assert.equal(a.imageCredit.kind, "ai");
    assert.equal(aiCreditText(a.imageCredit), "画像はイメージ（AI生成）");
  }
  // 新製品の発表で AI が製品の種類を描いた表紙は、発表の札
  const launch = shareImageArticle({ ...FUJIYA, coverCredit: { ...FUJIYA.coverCredit, launch: true } });
  assert.equal(aiCreditText(launch.imageCredit), "公式画像がないためイメージ（AI生成）");
});

test("記事の写真が AI の絵なら、話題とのつながりを確かめた coverImage を優先する", () => {
  const a = shareImageArticle({ ...FUJIYA, thumbnail: `${IMG}fujiya-x-aaaa1111.jpg`, imageCredit: { kind: "ai" } });
  assert.equal(a.thumbnail, FUJIYA.coverImage);
});

test("使える記事の写真（公式・素材）はそのまま。取得できないときだけ coverImage に回す", () => {
  const official = { ...FUJIYA, thumbnail: `${IMG}fujiya-beverage-price-increase-2027-bbbb2222.jpg`, imageCredit: { kind: "official", org: "不二家" }, heroOk: true };
  assert.equal(shareImageArticle(official), official);
  assert.equal(officialCreditText(shareImageArticle(official).imageCredit), "画像：不二家（公式発表より）");
  const stock = { ...official, imageCredit: { kind: "stock", creator: "x" } };
  assert.equal(shareImageArticle(stock), stock);
  assert.equal(shareImageArticle(official, true).thumbnail, FUJIYA.coverImage);
});

test("coverImage が無い・AI でない・地震の記事（noPhoto）は今までどおり（AI の絵を勝手に出さない）", () => {
  const none = { ...FUJIYA, coverImage: undefined, coverCredit: undefined };
  assert.equal(shareImageArticle(none), none);
  const notAi = { ...FUJIYA, coverCredit: { kind: "stock" } };
  assert.equal(shareImageArticle(notAi), notAi);
  const quake = { ...FUJIYA, noPhoto: true };
  assert.equal(shareImageArticle(quake), quake);
});

test("カバー・カードの画像の作り手が shareImageArticle を通し、URL の版も変わる（7日のキャッシュに古い暗い画像を残さない）", () => {
  assert.match(read("app/cover/[slug]/route.tsx"), /shareImageArticle\(found\)/);
  assert.match(read("app/cover/[slug]/route.tsx"), /shareImageArticle\(found, true\)/);
  assert.match(read("app/card/[slug]/route.tsx"), /shareImageArticle\(snsCardArticle\(found\)\)/);
  assert.ok(COVER_VERSION >= 4);
  assert.notEqual(coverPath(FUJIYA), coverPath({ ...FUJIYA, coverImage: `${IMG}other.jpg` }));
  assert.match(coverPath(FUJIYA), new RegExp(`\\?v=${COVER_VERSION}-`));
  const tp = read("scripts/threads_post.py");
  assert.match(tp, /CARD_VERSION = \d+/);
  assert.match(tp, /return cover_url\(article\)/);
});
