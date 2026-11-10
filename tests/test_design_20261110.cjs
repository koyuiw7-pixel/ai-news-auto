const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

// 台帳 W37（2026-11-10 オーナー決定）: 出典は小さくたたむ・広告の囲みは砂色の地と「PR」の札で本文と分ける・囲みの長い注記は出さない
const root = path.resolve(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(root, f), "utf8");

function loadFold() {
  const out = ts.transpileModule(read("lib/source-fold.ts"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", out)(mod, mod.exports);
  return mod.exports;
}
const { foldSourceLists } = loadFold();

test("[W37] 本文の出典の一覧は閉じた「出典を見る（N件）」にたたみ、URL の文字は名前にする（href は残す）", () => {
  const html =
    '<p>本文です。</p><ul><li>本文の一覧</li></ul><p>計算の出典は次のとおりです。</p>\n<ul>\n' +
    '<li>国税庁のタックスアンサー No.2523（<a href="https://www.nta.go.jp/taxes/shiraberu/taxanswer/gensen/2523.htm" target="_blank" rel="noopener noreferrer nofollow">https://www.nta.go.jp/taxes/shiraberu/taxanswer/gensen/2523.htm</a>）</li>\n' +
    "<li>国税庁の算出率の表（令和8年分）</li>\n" +
    '<li><a href="https://www.nenkin.go.jp/x.html">https://www.nenkin.go.jp/x.html</a></li>\n</ul>';
  const out = foldSourceLists(html);
  assert.match(out, /<details class="src-fold"><summary>出典を見る（3件）<\/summary>/);
  assert.doesNotMatch(out, /<details[^>]*\bopen\b/, "最初は閉じておく");
  assert.doesNotMatch(out, />https?:\/\//, "URL そのものを文字に出さない");
  assert.match(out, /href="https:\/\/www\.nta\.go\.jp\/taxes\/shiraberu\/taxanswer\/gensen\/2523\.htm"[^>]*>国税庁のタックスアンサー No\.2523<\/a><span class="src-host">nta\.go\.jp<\/span>/);
  assert.match(out, /href="https:\/\/www\.nenkin\.go\.jp\/x\.html">nenkin\.go\.jp<\/a>/);
  assert.match(out, /国税庁の算出率の表（令和8年分）/, "リンクの無い出典も消さない");
  assert.match(out, /<ul><li>本文の一覧<\/li><\/ul>/, "出典でない一覧はたたまない");
  assert.doesNotMatch(out, /計算の出典は次のとおりです/, "前置きは「出典を見る」に置き換える");
});

test("[W37] 出典の前置きでない段落の後の一覧・長い段落はそのまま", () => {
  const html = "<p>出典を確かめてから申し込むと、条件の違いが分かります。</p><ul><li>a</li></ul>";
  assert.equal(foldSourceLists(html), html);
  assert.equal(foldSourceLists("<p>手順は次のとおりです。</p><ul><li>a</li></ul>"), "<p>手順は次のとおりです。</p><ul><li>a</li></ul>");
});

test("[W37] 見出しの「出典」は目次の行き先なので残し、一覧だけたたむ", () => {
  const out = foldSourceLists('<h2 id="s">情報源</h2><ul><li><a href="https://openai.com/a">OpenAI</a></li></ul>');
  assert.match(out, /^<h2 id="s">情報源<\/h2><details class="src-fold"><summary>出典を見る（1件）<\/summary>/);
});

test("[W37] 記事ページ（今までの見た目・ノワール）の本文とかんたん版に出典のたたみを通す", () => {
  const page = read("app/articles/[slug]/page.tsx");
  assert.match(page, /const bodyHtmlRaw = foldSourceLists\(/);
  assert.match(page, /const easyHtml = easy \? foldSourceLists\(/);
});

test("[W37] 記事末の「出典と更新履歴」は小さな閉じた「出典を見る」（中身は HTML に残す）", () => {
  const src = read("components/SourceRecord.tsx");
  assert.match(src, /<details className="src-fold">/);
  assert.doesNotMatch(src, /<details[^>]*\bopen\b/);
  assert.match(src, /出典を見る（\$\{count\}件）/);
  assert.match(src, /確かめた資料/, "確かめた資料の欄は残す");
  const css = read("app/globals.css");
  assert.match(css, /\.src-fold \{[^}]*font-size: 0\.8125rem/);
});

test("[W37] 広告の囲みは砂色の地（.ad-box）と塗りの「PR」の札（.ad-pr）。ライト・ダークの両方に色がある", () => {
  const css = read("app/globals.css");
  assert.equal((css.match(/--ad-bg:/g) || []).length, 2, "ライトとダークの両方");
  assert.match(css, /\.ad-box \{[^}]*background: var\(--ad-bg\)/);
  assert.match(css, /\.ad-pr \{[^}]*background: var\(--ad-badge\)/);
  assert.match(read("components/rail/parts.tsx"), /<span className="ad-pr">PR<\/span>/);
  for (const f of ["components/ActionAd.tsx", "components/rail/RailRanking.tsx", "components/CompareOffers.tsx", "components/AffiliateBox.tsx", "components/CtaBanner.tsx"]) {
    assert.match(read(f), /ad-box/, `${f} に砂色の囲み`);
  }
});

test("[W37] 囲みの下の長い広告の注記は出さない（ページ冒頭の「本ページはプロモーションを含みます」と PR の札は残す）", () => {
  const banned = [
    /広告（アフィリエイトリンク）を含みます/,
    /申し込みがあると当サイトに紹介料が入ることがあります/,
    /価格・在庫・利用条件はリンク先でご確認ください/,
    /リンク経由の購入で当サイトに紹介料が入ることがあります/,
    /上記リンクはアフィリエイトリンクを含みます/,
    /当サイトは広告収入を得ています/,
  ];
  const files = [
    "components/ActionAd.tsx",
    "components/rail/parts.tsx",
    "components/rail/RailRanking.tsx",
    "components/CompareOffers.tsx",
    "components/AffiliateBox.tsx",
    "components/CtaBanner.tsx",
    "components/compare/parts.tsx",
  ];
  for (const f of files) {
    // コメントの中の引用（決定の記録）は数えない
    const code = read(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/^\s*\/\/.*$/gm, "");
    for (const re of banned) assert.doesNotMatch(code, re, `${f}: ${re}`);
  }
  assert.match(read("components/noir/NoirArticle.tsx"), /本ページはプロモーションを含みます/);
  assert.match(read("app/articles/[slug]/page.tsx"), /本ページはプロモーションを含みます/);
  assert.match(read("docs/owner_rules.md"), /^\| W37 \| \*\*2026-11-10 オーナー決定/m);
});
