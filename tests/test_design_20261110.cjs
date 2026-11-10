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

// 台帳 W38（2026-11-10 オーナー）: 広告の「得のカード」。数字は公式の出典と確認日つき・景品表示法の言葉を使わない・記事ごとの見出し
function loadBenefits() {
  const out = ts.transpileModule(read("lib/ad-benefits.ts").replace(/^import data from "@\/content\/ad_benefits\.json";/m, "const data = __DATA__;"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", "__DATA__", out)(mod, mod.exports, JSON.parse(read("content/ad_benefits.json")));
  return mod.exports;
}
const benefits = loadBenefits();
const benefitData = JSON.parse(read("content/ad_benefits.json"));

test("[W38] 得のカードの数字はすべて出典（https の公式ページかサイト内のページ）と確認日つき", () => {
  for (const [key, raw] of Object.entries(benefitData.offers)) {
    for (const chip of raw.chips ?? []) {
      const src = benefitData.sources[chip.src];
      assert.ok(src, `${key}: 出典 ${chip.src} が無い`);
      assert.match(src.url, /^(https:\/\/|\/)/, `${key}: ${src.url}`);
      assert.match(src.checkedAt, /^\d{4}-\d{2}-\d{2}$/, `${key}: 確認日`);
    }
    if (raw.use) assert.ok(benefitData.offers[raw.use], `${key}: use ${raw.use}`);
  }
  // 出典の無い数字は捨てる
  assert.equal(benefits.benefitFor("no-such-offer"), undefined);
});

test("[W38] 景品表示法で根拠なしに使えない言葉（最安・必ず・絶対・No.1・一番）を得のカードに書かない", () => {
  const text = JSON.stringify({ offers: benefitData.offers, articles: benefitData.articles });
  assert.doesNotMatch(text, benefits.BANNED_WORDS);
  // ふるさと納税の「2,000円」は「上限の中なら」の条件つきで見せる
  for (const row of benefitData.articles) for (const h of Object.values(row.headlines)) if (/2,000円/.test(h)) assert.match(h, /上限の中/, h);
});

test("[W38] ふるさと納税の上限の例は計算ツール（lib/calc-math.ts）と同じ数字", () => {
  const out = ts.transpileModule(read("lib/calc-math.ts"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", "require", out)(mod, mod.exports, require);
  const limit = mod.exports.furusatoLimit(300000, 10).limit;
  const chip = benefitData.offers.furusato.chips.find((c) => c.label === "上限の例");
  assert.equal(chip.value, `約${(Math.round(limit / 1000) / 10).toFixed(1)}万円`);
  assert.match(chip.sub, /所得割30万円・所得税率10%/);
});

test("[W38] 記事ごとの見出し（読者の状況）は記事の slug で決まり、ない記事は商品の見出しのまま", () => {
  const ca = benefits.benefitFor("rakuten-furusato", "child-allowance-december-payment");
  assert.match(ca.headline, /子育て世帯/);
  assert.equal(ca.chips[0].value, "2,000円");
  assert.ok(ca.sources.some((x) => x.url === "/tools/furusato-limit"), "上限の例は計算ツールが出典");
  assert.match(benefits.benefitFor("rakuten-furusato", "nencho-2026-changes").headline, /年末調整/);
  assert.equal(benefits.benefitFor("rakuten-furusato", "some-other-article").headline, undefined);
  assert.match(benefits.benefitFor("norton", "docomo-data-leak-what-to-do").headline, /流出/);
  assert.match(benefits.benefitFor("bb-excite", "pension-support-benefit-old-age-eligibility").headline, /年金/);
  const listed = benefits.withArticleBenefits([{ item: { key: "mf-kakutei" }, pixel: "p" }], "winter-bonus-take-home-pay-calculation");
  assert.equal(listed[0].pixel, "p", "枠の中身はそのまま");
  assert.match(listed[0].item.benefit.headline, /ボーナス/);
  // 見出しの正規表現が、今ある記事に当たる
  const contexts = fs
    .readdirSync(path.join(root, "content/articles"))
    .filter((f) => f.endsWith(".json"))
    .map((f) => {
      const a = JSON.parse(fs.readFileSync(path.join(root, "content/articles", f), "utf8"));
      return `${a.slug} ${a.title} ${a.seoTitle ?? ""}`;
    });
  for (const row of benefitData.articles) assert.ok(contexts.some((c) => new RegExp(row.match).test(c)), `当たる記事が無い: ${row.match}`);
  // 題名の語でも当たる（slug に語が無い記事にも広げる。2026-11-11 オーナー「今回の施策を大幅に広め」）
  assert.match(benefits.benefitFor("jackery", "some-quake-article 地震のあとに停電").headline, /停電/);
  assert.match(benefits.benefitFor("hikkoshi-samurai", "x 引っ越しの手続き").headline, /引っ越し/);
});

test("[W38] 記事・ガイド・計算ツールの PR に得のカードを付け、PrFeature が数字と出典を描く（クリックの置き場所 data-aff-pos は変えない）", () => {
  const page = read("app/articles/[slug]/page.tsx");
  assert.match(page, /actionAdWithBenefits\(actionAdForArticle\(article\), benefitContext\)/);
  assert.match(page, /const benefitContext = `\$\{article\.slug\} \$\{article\.title\}/);
  assert.match(page, /offerWithBenefits\(offerPlan\.rail, benefitContext\)/);
  assert.match(read("components/HowtoGuideView.tsx"), /actionAdWithBenefits\(rawAds\.top/);
  assert.match(read("app/tools/furusato-limit/page.tsx"), /actionAdWithBenefits\(toolAd\("furusato"\)/);
  const parts = read("components/rail/parts.tsx");
  assert.match(parts, /<BenefitNumbers benefit=\{benefit\} \/>/);
  assert.match(parts, /出典・確認日：/);
  assert.match(read("components/ActionAd.tsx"), /data-aff-pos=\{pos\}/);
});
