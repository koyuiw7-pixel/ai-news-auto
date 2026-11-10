// SEO A20（2026-11-10）: 小さな手入れ。タグの題名の空白・記事の外側の欄の見出し・古い標語・フィード・/newsletter
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');

test('[A20] タグの題名・h1・説明に「年金 の最新」のような半角の空白が無い。題名に本数を入れない', () => {
  const view = read('app/tags/[tag]/view.tsx');
  assert.doesNotMatch(view, /\{label\} の最新/);
  assert.doesNotMatch(view, /\{label\} に/);
  assert.match(view, /title: `\$\{label\}の最新ニュース・解説記事\$\{pageSuffix\(page\)\}`/);
  assert.match(view, /articles\.slice\(0, 2\)/, '説明文は新しい記事2本の題名から');
});

test('[A20] 記事の外側の欄（関連記事・次に読む・この話の続き・よく読まれている・メール配信）の見出しは h2 にしない', () => {
  for (const [rel, id] of [
    ['components/noir/NoirArticle.tsx', 'related-heading'],
    ['app/articles/[slug]/page.tsx', 'related-heading'],
    ['components/NextRead.tsx', 'next-read-heading'],
    ['components/noir/StoryLinks.tsx', 'story-links-heading'],
    ['components/noir/NoirPopular.tsx', 'nr-pop-heading'],
  ]) {
    const src = read(rel);
    assert.doesNotMatch(src, new RegExp(`<h2 id="${id}"`), rel);
    assert.match(src, new RegExp(`<p id="${id}"`), rel);
  }
  assert.doesNotMatch(read('components/NewsletterSignup.tsx'), /<h2/);
});

test('[A20] 古い標語「どこよりも速く」が残っていない', () => {
  for (const dir of ['app', 'lib', 'components']) {
    const walk = (d) => fs.readdirSync(path.join(root, d), { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));
    for (const rel of walk(dir).filter((f) => /\.(tsx?|mjs|css)$/.test(f))) assert.doesNotMatch(read(rel), /どこよりも速く/, rel);
  }
  assert.doesNotMatch(read('site.config.ts'), /どこよりも速く/);
});

test('[A20] /feed.xml に作成者・画像・最終更新、/newsletter はサイトマップに', () => {
  const feed = read('app/feed.xml/route.ts');
  assert.match(feed, /<dc:creator>/);
  assert.match(feed, /<enclosure url=/);
  assert.match(feed, /<lastBuildDate>/);
  assert.match(feed, /xmlns:dc="http:\/\/purl\.org\/dc\/elements\/1\.1\/"/);
  assert.match(read('lib/sitemap.ts'), /"\/newsletter"\]\.map\(fixed\)/);
});
