// 本文の図（記事 JSON の figures。lib/figures.ts）と、ノワールの記事ページの並び（2026-11-09 オーナー）
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const root = path.join(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');
function load(rel) {
  const filename = path.join(root, rel);
  const compiled = ts.transpileModule(read(rel), { compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
  const m = new Module(filename, module);
  m.filename = filename;
  m.paths = module.paths;
  m._compile(compiled, filename);
  return m.exports;
}
const figures = load('lib/figures.ts');

test('図は見出しの章の終わり（次の見出しの手前）に置く。見出しが無い・よその画像は出さない', () => {
  const html = '<h2>支給額</h2><p>a</p><h2>支給月</h2><p>b</p>';
  const out = figures.insertArticleFigures(html, [
    { src: '/fig/x-fig1.png', alt: '支給額の図', caption: '図：サイソク作成', after_heading: '支給額' },
    { src: 'https://example.com/a.png', after_heading: '支給月' },
    { src: '/fig/x-fig2.png', after_heading: '無い見出し' },
  ], '題');
  assert.match(out, /^<h2>支給額<\/h2><p>a<\/p><figure class="body-figure art-fig not-prose"><img src="\/fig\/x-fig1.png" alt="支給額の図"[^>]*><figcaption class="text-note">図：サイソク作成<\/figcaption><\/figure><h2>支給月<\/h2>/);
  assert.doesNotMatch(out, /example\.com|x-fig2/);
  // 最後の章なら本文の終わりに
  assert.match(figures.insertArticleFigures(html, [{ src: '/fig/x-fig3.webp', after_heading: '支給月' }], '題'), /<p>b<\/p><figure/);
});

test('ノワール: 題名 → 写真 → 要点 → すぐにできること → 1つ目の PR → なるほど → 本文。PC は右の列（追従）', () => {
  const page = read('components/noir/NoirArticle.tsx');
  const order = ['<h1>{title}</h1>', 'nr-cover', 'className="nr-sum"', '{slots.quick}', '{slots.adEarly', '{slots.afterSummary}', 'id="nr-body"', '{slots.adMidPr', '{slots.midBoxes}', '{slots.adEnd', 'related-heading', 'nr-aside'];
  let at = -1;
  for (const part of order) {
    const i = page.indexOf(part);
    assert.ok(i > at, `${part} の位置`);
    at = i;
  }
  const css = read('components/noir/noir.css');
  assert.match(css, /@media \(min-width: 1024px\) \{\s*\.noir \.nr-wrap \{[^}]*grid-template-columns: minmax\(0, 1fr\) 320px/);
  assert.match(css, /\.noir \.nr-sticky \{[^}]*position: sticky/);
  // 本文の列の PR は最大3つ。スマホ用の写しは表示を数えない（右の列で1回だけ数える）
  const ctx = read('components/noir/noirArticlePage.tsx');
  assert.match(ctx, /adBlocks\.slice\(0, 3\)/);
  assert.match(ctx, /<RailRanking offer=\{offer\} pos="ranking-end" countImpression=\{false\} \/>/);
});
