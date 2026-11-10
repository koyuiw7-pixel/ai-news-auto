// /llms.txt を今のサイト（暮らしとお金の「自分ごと」ニュース）に合わせる（2026-11-10 LLMO-A14）。
// 実際に GET() を動かして、中身を確かめる。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const root = path.join(__dirname, '..');
const cache = new Map();
function load(rel) {
  const filename = path.join(root, rel);
  if (cache.has(filename)) return cache.get(filename).exports;
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const m = new Module(filename, module);
  m.filename = filename;
  m.paths = module.paths;
  cache.set(filename, m);
  const origRequire = m.require.bind(m);
  m.require = (spec) => {
    let target = null;
    if (spec.startsWith('@/')) target = spec.slice(2);
    else if (spec.startsWith('./') || spec.startsWith('../')) target = path.relative(root, path.join(path.dirname(filename), spec));
    if (target !== null) {
      for (const ext of ['.ts', '.tsx', '']) {
        const p = path.join(root, target + ext);
        if (fs.existsSync(p) && fs.statSync(p).isFile()) return p.endsWith('.json') ? JSON.parse(fs.readFileSync(p, 'utf8')) : load(path.relative(root, p));
      }
    }
    return origRequire(spec);
  };
  m._compile(compiled, filename);
  return m.exports;
}

let body;
async function llms() {
  if (body === undefined) body = await load('app/llms.txt/route.ts').GET().text();
  return body;
}

test('[LLMO-A14] 1行目は「# サイソクニュース」だけ（古い宣伝文を付けない）', async () => {
  const text = await llms();
  assert.equal(text.split('\n')[0], '# サイソクニュース');
  const { siteConfig } = load('site.config.ts');
  assert.ok(text.includes(`> ${siteConfig.description}`));
});

test('[LLMO-A14] 「使えるか」の判定の説明を出さない・全角の縦棒を出さない', async () => {
  const text = await llms();
  assert.doesNotMatch(text, /「使えるか」の判定|判定は発表時点/);
  assert.ok(!text.includes('｜'), '全角の縦棒');
});

test('[LLMO-A14] 見出しのすぐ下に見出しが来ない（中身の無い章は出さない）', async () => {
  const lines = (await llms()).split('\n').filter((l) => l.trim() !== '');
  for (let i = 0; i + 1 < lines.length; i++) {
    if (lines[i].startsWith('#')) assert.ok(!lines[i + 1].startsWith('#'), `${lines[i]} → ${lines[i + 1]}`);
  }
});

test('[LLMO-A14] 章の順番と、載せるページ（編集方針・計算ツール・ガイド50本以上）', async () => {
  const text = await llms();
  const headings = text.split('\n').filter((l) => l.startsWith('## ')).map((l) => l.slice(3));
  const order = ['このサイトについて', '手続きとお金のガイド', '計算ツール', 'ジャンル', '最新の記事', 'Optional'];
  const present = order.filter((h) => headings.includes(h));
  assert.deepEqual(headings, present, '決めた章だけ、この順で');
  assert.equal(headings[headings.length - 1], 'Optional');
  for (const p of ['/about)', '/editorial-policy)', '/corrections)', '/tools/furusato-limit)', '/tools/defense-tax)']) assert.ok(text.includes(p), p);
  assert.ok((text.match(/\/guides\//g) ?? []).length >= 50, 'ガイドへのリンクが50本以上');
  // 手続きとお金のガイドは Optional より前（AIの製品ページは最後）
  const optionalAt = text.indexOf('## Optional');
  const procedure = load('lib/howto.ts').getAllHowtos().filter((g) => g.kind === 'procedure');
  assert.ok(procedure.length > 0);
  for (const g of procedure) {
    const at = text.indexOf(`/guides/${g.slug})`);
    assert.ok(at > 0 && at < optionalAt, g.slug);
  }
});

test('[LLMO-A14] 最新の記事は検索に出す記事だけ40本まで、題名は articleTitle()（題名は1つだけ。A29）', async () => {
  const text = await llms();
  const { getAllArticles } = load('lib/articles.ts');
  const { isIndexable } = load('lib/indexing.ts');
  const { articleTitle } = load('lib/headline.ts');
  const start = text.indexOf('## 最新の記事');
  assert.ok(start > 0);
  const block = text.slice(start, text.indexOf('\n## ', start + 1));
  const items = [...block.matchAll(/^- \[(.*)\]\(https?:\/\/[^)]+\/articles\/([^)]+)\)/gm)];
  assert.ok(items.length > 0 && items.length <= 40);
  const bySlug = new Map(getAllArticles().map((a) => [a.slug, a]));
  for (const [, title, slug] of items) {
    const article = bySlug.get(slug);
    assert.ok(article && isIndexable(article), slug);
    const expected = articleTitle(article).replace(/｜/g, '　').replace(/\s+/g, ' ').trim();
    assert.equal(title, expected, slug);
  }
});
