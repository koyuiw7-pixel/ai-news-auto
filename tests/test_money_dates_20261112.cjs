// 暮らしとお金の日程ページ（/dates/[slug]。2026-11-12）
// - 日付・金額は公式のページだけを出典にする（出典の URL は官公庁・発表元の公式ドメインだけ）
// - 答え・出典・確認日は、ページの最初の見出し（h2）より前に出す（スマホの最初の画面）
// - 催しではないので schema.org の Event を出さない。FAQPage の問いはページに見えているものだけ
// - リンク先・関連記事は実在するものだけ。「｜」「ざっくり」は使わない
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const root = path.join(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');

const compile = (m, filename) => {
  const out = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
    fileName: filename,
  }).outputText;
  m._compile(out, filename);
};
require.extensions['.ts'] = compile;
require.extensions['.tsx'] = compile;
require.extensions['.css'] = () => {};
const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, ...rest) {
  if (request.startsWith('@/')) request = path.join(root, request.slice(2));
  return origResolve.call(this, request, parent, ...rest);
};

const raw = read('content/money-dates.json');
const { dates } = JSON.parse(raw);
// 官公庁（go.jp・lg.jp）と、発表元の会社・団体の公式ドメインだけ（2026-11-12 ニッチの問いのページで発表元を追加）
const OFFICIAL = /^https:\/\/([a-z0-9-]+\.)*(go\.jp|lg\.jp|japanpost\.jp|aboutamazon\.jp|docomo\.ne\.jp|bk\.mufg\.jp|giroj\.or\.jp|sompo-japan\.co\.jp|y-yokohama\.com|srigroup\.co\.jp|suntory\.co\.jp|fujiya-peko\.co\.jp|pietro\.co\.jp|otsukafoods\.co\.jp|pasconet\.co\.jp|housefoods-group\.com|ideco-koushiki\.jp)\//;

test('日程ページのデータ: 出典は公式のページ、確認日あり、禁止の文字なし', () => {
  assert.ok(dates.length >= 6, '6ページ以上');
  assert.doesNotMatch(raw, /｜|ざっくり/);
  const slugs = new Set();
  for (const d of dates) {
    assert.ok(!slugs.has(d.slug), `slug の重複 ${d.slug}`);
    slugs.add(d.slug);
    assert.match(d.verifiedAt, /^\d{4}-\d{2}-\d{2}$/, d.slug);
    assert.ok(d.answer.items.length > 0 && d.answer.items.length <= 3, `${d.slug}: 答えは1〜3行`);
    const urls = [d.answer.source.url, ...d.sources.map((s) => s.url), ...d.answers.flatMap((a) => (a.sources ?? []).map((s) => s.url))];
    if (d.after) urls.push(d.after.answer.source.url);
    for (const url of urls) assert.match(url, OFFICIAL, `${d.slug}: 公式でない出典 ${url}`);
    assert.ok(!Number.isNaN(Date.parse(d.after?.at ?? '2026-01-01T00:00:00Z')), d.slug);
    assert.doesNotThrow(() => new RegExp(d.match), d.slug);
    for (const t of [d.answer.table, ...(d.tables ?? [])].filter(Boolean)) {
      assert.ok(t.columns.length >= 2 && t.rows.length > 0, `${d.slug}: 表が空`);
      for (const row of t.rows) assert.equal(row.length, t.columns.length, `${d.slug}: 表の列の数が合わない ${row[0]}`);
    }
    for (const t of d.tables ?? []) assert.match(t.source.url, OFFICIAL, `${d.slug}: 表の出典が公式でない`);
    for (const step of d.howToCheck ?? []) assert.ok(step.length > 10, `${d.slug}: 確かめ方が短すぎる`);
  }
});

test('日程ページのリンク先・関連記事は実在する', () => {
  const exists = (href) => {
    const [kind, slug] = href.replace(/^\//, '').split('/');
    if (kind === 'guides') return fs.existsSync(path.join(root, 'content/howto', `${slug}.json`)) || fs.existsSync(path.join(root, 'content/guides', `${slug}.json`));
    if (kind === 'tools') return fs.existsSync(path.join(root, 'app/tools', slug, 'page.tsx'));
    if (kind === 'dates') return dates.some((d) => d.slug === slug);
    if (kind === 'articles') return fs.existsSync(path.join(root, 'content/articles', `${slug}.json`));
    if (kind === 'roundups') return fs.existsSync(path.join(root, 'app/roundups/[kind]/page.tsx'));
    return false;
  };
  for (const d of dates) {
    for (const link of d.links) assert.ok(exists(link.href), `${d.slug}: 無いページ ${link.href}`);
    for (const slug of d.articles) assert.ok(exists(`/articles/${slug}`), `${d.slug}: 無い記事 ${slug}`);
  }
  // 計算ツールのページから期限のページへ
  assert.match(read('app/tools/furusato-limit/page.tsx'), /\/dates\/furusato-nozei-2026-deadline/);
  assert.match(read('components/Footer.tsx'), /href: "\/dates"/);
});

test('時刻を過ぎたら答えを差し替える（古い答えを出し続けない）', () => {
  const lib = require(path.join(root, 'lib/money-dates.ts'));
  const bond = lib.getMoneyDate('kojin-muke-kokusai');
  assert.ok(bond.after);
  const before = Date.parse(bond.after.at) - 1;
  const after = Date.parse(bond.after.at) + 1;
  assert.equal(lib.currentAnswer(bond, before), bond.answer);
  assert.equal(lib.currentAnswer(bond, after), bond.after.answer);
  assert.equal(lib.currentTitle(bond, after), bond.titleAfter);
  const pension = lib.getMoneyDate('nenkin-december-2026');
  assert.equal(lib.daysUntilKey(pension, Date.parse('2026-12-14T15:00:00Z')), 0);
  assert.equal(lib.daysUntilKey(pension, Date.parse('2026-12-13T15:00:00Z')), 1);
  assert.equal(lib.daysUntilKey(pension, Date.parse('2026-12-15T15:00:00Z')), null);
});

const ldOf = (html) => [...html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1])).flat();
const unescape = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'");
const textOf = (html) => unescape(html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ''));

test('日程ページを実際に描く: 答え・出典・確認日が最初の見出しより前、Event なし、FAQ の問いは見えている', async () => {
  const { renderToStaticMarkup } = require('react-dom/server');
  const Page = require(path.join(root, 'app/dates/[slug]/page.tsx')).default;
  const lib = require(path.join(root, 'lib/money-dates.ts'));
  for (const d of dates) {
    const html = renderToStaticMarkup(await Page({ params: Promise.resolve({ slug: d.slug }) }));
    const ld = ldOf(html);
    assert.equal(ld.filter((x) => x['@type'] === 'Event').length, 0, `${d.slug}: Event を出さない`);
    assert.ok(ld.some((x) => x['@type'] === 'Article'), d.slug);
    assert.ok(ld.some((x) => x['@type'] === 'BreadcrumbList'), d.slug);
    const faqs = ld.filter((x) => x['@type'] === 'FAQPage');
    assert.equal(faqs.length, 1, d.slug);
    const text = textOf(html);
    for (const q of faqs[0].mainEntity) {
      assert.ok(text.includes(q.name), `${d.slug}: 見えない問い「${q.name}」`);
      assert.ok(text.includes(q.acceptedAnswer.text), `${d.slug}: 見えない答え`);
    }
    const head = textOf(html.slice(0, html.indexOf('<h2')));
    const answer = lib.currentAnswer(d);
    for (const item of answer.items) assert.ok(head.includes(item.value), `${d.slug}: 答え「${item.value}」が最初の見出しより後`);
    assert.ok(head.includes(answer.source.title), `${d.slug}: 出典が最初の画面にない`);
    // 一覧の答え（表）も最初の見出しより前に出す
    for (const row of answer.table?.rows ?? []) assert.ok(head.includes(row[0]), `${d.slug}: 表の行「${row[0]}」が最初の見出しより後`);
    if ((d.howToCheck ?? []).length > 0) assert.ok(text.includes('自分の場合はどう確かめる？'), `${d.slug}: 確かめ方の見出しがない`);
    assert.ok(head.includes(`確認日 ${d.verifiedAt.replaceAll('-', '/')}`), `${d.slug}: 確認日が最初の画面にない`);
    assert.doesNotMatch(text, /｜|ざっくり|undefined/);
  }
});

test('サイトマップ・シェア画像・IndexNow・流入の数え方に日程ページが入っている', () => {
  const { sitemapEntries } = require(path.join(root, 'lib/sitemap.ts'));
  const { siteConfig } = require(path.join(root, 'site.config.ts'));
  const urls = sitemapEntries().map((e) => e.url);
  assert.ok(urls.includes(`${siteConfig.url}/dates`));
  for (const d of dates) assert.ok(urls.includes(`${siteConfig.url}/dates/${d.slug}`), d.slug);
  const share = require(path.join(root, 'lib/page-share-items.ts'));
  for (const d of dates) {
    assert.ok(share.allShareKeys().includes(`date-${d.slug}`), d.slug);
    assert.equal(share.shareFor(`date-${d.slug}`).heading, d.name);
  }
  assert.ok(share.allShareKeys().includes('dates'));
  assert.match(read('scripts/indexnow.py'), /DATES_PATH = ROOT \/ "content" \/ "money-dates\.json"/);
  const { pageKey, isArticleKey } = require(path.join(root, 'lib/inflow.ts'));
  assert.equal(pageKey('/dates/nenkin-december-2026'), 'dates--nenkin-december-2026');
  assert.ok(!isArticleKey('dates--nenkin-december-2026'));
});
