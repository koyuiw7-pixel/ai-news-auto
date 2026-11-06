// 新しい記事の見た目「ノワール」（2026-11-07 オーナー承認・台帳 W36）。
// 今ある記事はそのまま・新しい記事だけ新しい見た目。決まった型の見出しを出さない。色は白・冷たい灰色・黒・赤1色。
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

const noir = load('lib/noir.ts');

test('[W36] 見た目を切り替えるのは layout: "noir" の印だけ（印の無い今までの記事は今までの見た目）', () => {
  assert.equal(noir.isNoir({ layout: 'noir' }), true);
  assert.equal(noir.isNoir({}), false);
  assert.equal(noir.isNoir({ layout: undefined }), false);
  const page = read('app/articles/[slug]/page.tsx');
  // 分かれ道は1か所。ノワールでなければ、今までの見た目（max-w-[1240px] の2列）をそのまま返す
  assert.equal((page.match(/isNoir\(article\)/g) ?? []).length, 1);
  assert.match(page, /if \(isNoir\(article\) && !isRoundup && web\) \{\s*return noirArticlePage\(/);
  assert.match(page, /return \(\s*<div className="mx-auto max-w-\[1240px\] px-5 py-8 sm:px-8 sm:py-10">/);
  // 今までの見た目の中身（要点・判定・目次・本文）は、ノワールの分かれ道の後ろにそのまま残っている
  const old = page.slice(page.indexOf('return (\n    <div className="mx-auto max-w-[1240px]'));
  for (const part of ['id="points-heading"', '<VerdictCard', 'id="toc-heading"', '<Highlight text={articleTitle(article)} />']) assert.ok(old.includes(part), part);
});

test('[W36] 今ある記事（2026-11-07 より前に載せた記事）には layout の印を付けない', () => {
  const dir = path.join(root, 'content/articles');
  const bad = [];
  for (const name of fs.readdirSync(dir)) {
    if (!name.endsWith('.json')) continue;
    const a = JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8'));
    if (a.layout && String(a.generatedAt || a.publishedAt) < '2026-11-06T16:00:00') bad.push(name);
  }
  assert.deepEqual(bad, []);
});

test('[W36] 表紙の写真は、大きな文字の無い公式の本物の写真と判定済みのものだけ（バナー・AI の絵・フリー素材・未判定は黒い表紙に題名）', () => {
  assert.equal(noir.noirPhoto({ thumbnail: '/img/a.jpg', imageCredit: { kind: 'official', org: '日産' }, heroOk: true }), '/img/a.jpg');
  // 告知のバナー・スライドなど（heroOk: false）と、未判定の写真は黒い表紙
  assert.equal(noir.noirPhoto({ thumbnail: '/img/a.jpg', imageCredit: { kind: 'official', imageKind: 'banner' }, heroOk: false }), null);
  assert.equal(noir.noirPhoto({ thumbnail: '/img/a.jpg', imageCredit: { kind: 'official', org: '日産' } }), null);
  assert.equal(noir.noirPhoto({ thumbnail: '/img/a.jpg', imageCredit: { kind: 'ai' } }), null);
  assert.equal(noir.noirPhoto({ thumbnail: '/img/a.jpg', imageCredit: { kind: 'stock' } }), null);
  assert.equal(noir.noirPhoto({ thumbnail: '', imageCredit: { kind: 'official' } }), null);
});

test('[W36] 要点の1文は **…** の数字だけを強調する', () => {
  assert.deepEqual(noir.splitEmphasis('LUXIONが**20万1,300円**値下げ'), { before: 'LUXIONが', em: '20万1,300円', after: '値下げ' });
  assert.deepEqual(noir.splitEmphasis('数字の無い文'), { before: '数字の無い文', em: null, after: '' });
});

test('[W36] 本文の仕上げ: 「まだ分からないこと」の章を外し、前と今の表は1行ずつ、まとめの表は一覧に', () => {
  const html = [
    '<h2>LUXIONは20万円安く</h2><p>本文。</p>',
    '<table><thead><tr><th>比べること</th><th>前</th><th>今回</th></tr></thead><tbody><tr><td>価格</td><td>499万8,400円</td><td><strong>479万7,100円</strong></td></tr></tbody></table>',
    '<table><thead><tr><th>グレード</th><th>価格</th></tr></thead><tbody><tr><td>X</td><td>3,932,500円</td></tr></tbody></table>',
    '<table><thead><tr><th>a</th><th>b</th><th>c</th></tr></thead><tbody><tr><td>1</td><td>2</td><td>3</td></tr></tbody></table>',
    '<h2>まだ分からないこと</h2><ul><li>発売日はまだ発表されていません</li></ul>',
    '<h2>グレードごとに</h2><table><thead><tr><th>グレード</th><th>内容</th></tr></thead><tbody><tr><td>LUXION</td><td>寒さ対策の装備が標準に</td></tr></tbody></table>',
  ].join('');
  const out = noir.noirBodyHtml(html, {
    changes: [{ label: '価格', before: '499万8,400円', after: '479万7,100円' }],
    wrapUp: [{ name: 'LUXION', text: '寒さ対策の装備が標準に' }],
  });
  assert.doesNotMatch(out, /まだ分からない|発売日はまだ/);
  assert.match(out, /<div class="nr-chg rv" data-dense=""><div class="nr-c"><small>価格<\/small><p><s>499万8,400円<\/s><i aria-label="から">→<\/i><b>479万7,100円<\/b><\/p><\/div><\/div>/);
  assert.match(out, /<ul class="nr-line rv" data-dense=""><li><b>LUXION<\/b><span>寒さ対策の装備が標準に<\/span><\/li><\/ul>/);
  assert.match(out, /<table class="nr-price rv">/); // 2列の表は細い線の表
  assert.match(out, /<div class="nr-scroll rv"><table>/); // 3列以上は横に動かせる枠
  assert.match(out, /<h2 data-rv="">グレードごとに/);
  // 欄が無ければ表はそのまま（空の囲みを作らない）
  const plain = noir.noirBodyHtml('<table><tr><td>価格</td><td>1円</td><td>2円</td></tr></table>', {});
  assert.doesNotMatch(plain, /nr-chg|nr-line/);
  assert.equal(noir.escapeHtml('<a&"'), '&lt;a&amp;&quot;');
});

test('[W36] ノワールに決まった型の見出し（「このニュースを3行で」「何が起きた」「いくらになる」「まだ分からないこと」「KEY NUMBERS」）を出さない', () => {
  const files = ['components/noir/NoirArticle.tsx', 'components/noir/noirArticlePage.tsx', 'components/noir/noir.css'];
  for (const rel of files) {
    const src = read(rel).split('\n').filter((line) => !/^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line)).join('\n');
    for (const bad of ['このニュースを3行で', '何が起きた', 'いくらになる', 'まだ分からないこと', 'KEY NUMBERS', 'POINTS', '3行で']) {
      assert.ok(!src.includes(bad), `${rel}: ${bad}`);
    }
  }
});

test('[W36] 色は白・冷たい灰色・黒と、差し色の赤だけ（クリーム・ベージュ・金を使わない）', () => {
  const css = read('components/noir/noir.css');
  const allowedRed = new Set(['#ff1f3d', '#d7001f']);
  for (const hex of css.match(/#[0-9a-fA-F]{6}\b/g) ?? []) {
    const h = hex.toLowerCase();
    if (allowedRed.has(h)) continue;
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    // 灰色: 赤みが青みを上回らない（暖かい色・クリームにしない）・色の差が小さい
    assert.ok(r <= b + 2 && Math.max(r, g, b) - Math.min(r, g, b) <= 16, `${hex} は灰色でも差し色の赤でもない`);
  }
  for (const m of css.matchAll(/rgb\((\d+) (\d+) (\d+)/g)) {
    const [r, g, b] = m.slice(1).map(Number);
    if (r === 255 && g === 31 && b === 61) continue; // 赤の薄い地（蛍光ペンの代わり）
    assert.ok(Math.max(r, g, b) - Math.min(r, g, b) <= 16, `rgb(${r} ${g} ${b})`);
  }
  assert.doesNotMatch(css, /cream|beige|gold|ivory|#f[5-9a-f]f[0-9a-f]e[0-9a-f]/i);
});

test('[W36] 黒の上に赤い文字を置かない（黒い表紙・黒いカード・黒いボタンの文字は白。赤は線と札の地色だけ）', () => {
  const css = read('components/noir/noir.css');
  const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({ sel: m[1].trim(), body: m[2] }));
  for (const { sel, body } of rules) {
    const onBlack = /nr-hero|nr-s2|nr-srcbtn|nr-kick|nr-top(?!\.solid)/.test(sel) && !/\.solid/.test(sel);
    if (!onBlack) continue;
    assert.doesNotMatch(body, /(^|[;\s])color:\s*var\(--nr-(red|deep)\)/, `${sel} の文字が赤`);
  }
  // 暗い画面では紙面も黒いので、赤い文字（続きを読む・矢印）を白・灰色にする
  assert.match(css, /:root\[data-theme="dark"\] \.noir \{[^}]*--nr-link: #ffffff/);
  assert.match(css, /:root\[data-theme="dark"\] \.noir \.nr-chg i \{\s*color: var\(--nr-soft\)/);
});

test('[W36] 動きを減らす設定に従う・ノワールの CSS は .noir の中だけに効く（今までの記事の見た目を変えない）', () => {
  const css = read('components/noir/noir.css');
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  const rules = [...css.replace(/@media[^{]+\{/g, '').replace(/@keyframes[^{]+\{[^{}]*(\{[^{}]*\}[^{}]*)*\}/g, '').matchAll(/([^{}]+)\{[^{}]*\}/g)].map((m) => m[1].trim());
  for (const sel of rules) {
    for (const part of sel.split(',').map((s) => s.trim()).filter(Boolean)) {
      if (/^(from|to|\d+%)$/.test(part)) continue;
      assert.match(part, /\.noir|html:has\(\.noir\)/, `.noir の外に効く決まり: ${part}`);
    }
  }
});
