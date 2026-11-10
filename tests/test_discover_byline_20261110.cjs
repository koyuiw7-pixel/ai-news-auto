// Google Discover・Google ニュースの準備（2026-11-10）。
// ①記事の題名のすぐ下に署名（編集した媒体＋/about へのリンク＋公開の日付と時刻、更新が違えば更新の日時）
// ②公式の写真が無く、表紙の写真のイメージ（Muse の写真など）がある記事は、その写真（16:9・札だけ）を og:image と NewsArticle の image の先頭に
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const root = path.join(__dirname, '..');
require.extensions['.ts'] = (m, filename) => {
  m._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
};
function load(rel) {
  const filename = path.join(root, rel);
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
  const m = new Module(filename, module);
  m.filename = filename;
  m.paths = module.paths;
  m._compile(compiled, filename);
  return m.exports;
}
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');

const MUSE = 'https://ai-tech-express.jp/img/electricity-bill-muse-cf88fa2b.jpg';
const FIGURE = 'https://ai-tech-express.jp/img/electricity-bill-figure-966b9d85.jpg';
const museArticle = {
  slug: 'electricity-bill',
  thumbnail: FIGURE,
  imageCredit: { kind: 'figure', imageKind: 'cover', width: 1200, height: 630 },
  coverImage: MUSE,
  coverCredit: { kind: 'ai', model: 'muse' },
};

test('表紙の写真のイメージ（Muse）がある記事は、16:9 の写真の共有画像が先・見出し入りのカバーが2つ目（文字の多い図より先）', () => {
  const { shareImages, photoSharePath } = load('lib/share-image.ts');
  const images = shareImages(museArticle, '/cover/electricity-bill?v=5-x', '題名');
  assert.match(images[0].url, /^\/cover\/electricity-bill\/photo\?v=\d+-[0-9a-z]+$/);
  assert.deepEqual([images[0].width, images[0].height], [1200, 675]);
  assert.equal(images[1].url, '/cover/electricity-bill?v=5-x');
  // URL は写真が替わると変わる（古い画像のキャッシュを使わせない）。cloudflare/worker.ts の immutable の形（?v=数字-英数字）
  const other = photoSharePath({ ...museArticle, coverImage: MUSE.replace('cf88fa2b', 'aaaa1111') });
  assert.notEqual(other, images[0].url);
});

test('公式の写真がある記事は今までどおり公式の写真が先（表紙のイメージより優先）', () => {
  const { shareImages } = load('lib/share-image.ts');
  const photo = 'https://ai-tech-express.jp/img/electricity-bill-1a2b3c4d.jpg';
  const images = shareImages({ ...museArticle, thumbnail: photo, imageCredit: { kind: 'official', width: 1200, height: 800 } }, '/cover/x?v=1', '題名');
  assert.equal(images[0].url, photo);
});

test('表紙のイメージが無い・地震の記事・外部の画像は、写真の共有画像を作らない（図・カバーのまま）', () => {
  const { shareImages, photoCover } = load('lib/share-image.ts');
  const noCover = { ...museArticle, coverImage: '', coverCredit: null };
  assert.equal(photoCover(noCover), null);
  assert.equal(shareImages(noCover, '/cover/x?v=1', '題名')[0].url, '/cover/x?v=1');
  assert.equal(photoCover({ ...museArticle, noPhoto: true }), null);
  assert.equal(photoCover({ ...museArticle, coverImage: 'https://example.com/a.jpg' }), null);
  assert.equal(photoCover({ ...museArticle, coverCredit: { kind: 'stock' } }), null);
});

test('写真の共有画像は AI の札を付け、見出しの文字は重ねない（台帳 I4）。/cover の下なのでフォントの先読み・キャッシュはカバーと同じ', () => {
  const route = read('app/cover/[slug]/photo/route.tsx');
  assert.match(route, /aiCreditText\(article\.coverCredit\)/);
  assert.match(route, /PHOTO_SHARE_WIDTH as WIDTH/);
  assert.doesNotMatch(route, /articleTitle|splitTitle/);
  const worker = read('cloudflare/worker.ts');
  assert.match(worker, /url\.pathname\.startsWith\("\/cover\/"\)[\s\S]{0,200}loadFonts/);
});

test('NewsArticle の image も同じ順（写真の共有画像があれば先頭）', () => {
  const page = read('app/articles/[slug]/page.tsx');
  assert.match(page, /image: \(photoSharePath\(article\)\s*\?\s*\[photoSharePath\(article\), coverPath\(article\)\]/);
});

test('署名の日時: 公開は datePublished と同じ時刻、更新は分単位で違うときだけ', () => {
  const { bylineDates } = load('lib/byline.ts');
  const d = bylineDates({ generatedAt: '2026-11-09T17:18:21+00:00', publishedAt: '2026-11-09T17:17:25+00:00', updatedAt: '2026-11-09T18:44:20+00:00' });
  assert.equal(d.published, '2026-11-09T17:18:21+00:00');
  assert.equal(d.publishedLabel, '2026/11/10 02:18');
  assert.equal(d.updatedLabel, '2026/11/10 03:44');
  assert.equal(bylineDates({ generatedAt: '2026-11-09T17:18:21+00:00', updatedAt: '2026-11-09T17:18:40+00:00' }).updated, null);
  assert.equal(bylineDates({ generatedAt: '2026-11-09T17:18:21+00:00', updatedAt: '2026-11-08T00:00:00+00:00' }).updated, null);
  assert.equal(bylineDates({}), null);
});

test('どちらの記事の形も、題名のすぐ下に署名（編集した媒体 → /about と公開の日時）。人が確かめたとは書かない', () => {
  const noir = read('components/noir/NoirArticle.tsx');
  const h1 = noir.indexOf('<h1>{title}</h1>');
  const header = noir.slice(h1, noir.indexOf('</header>', h1));
  assert.match(header, /編集：<Link href="\/about" rel="author">\{siteConfig\.author\}<\/Link>/);
  assert.match(header, /公開 <time dateTime=\{dates\.published\}>/);
  assert.match(header, /更新 <time dateTime=\{dates\.updated\}>/);
  const page = read('app/articles/[slug]/page.tsx');
  const ph1 = page.indexOf('<h1 className="t-h1 headline');
  const byline = page.slice(ph1, page.indexOf('</p>', ph1));
  assert.match(byline, /制作：<Link href="\/about" rel="author"/);
  assert.match(byline, /公開 <time dateTime=\{dates\.published\}>/);
  for (const text of [header, byline]) assert.doesNotMatch(text, /人が確認|担当者が確認|記者が確認|監修/);
});
