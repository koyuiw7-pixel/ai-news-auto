// Google Discover の基本（2026-11-04 オーナー承認のピボット・台帳 W32）。
// robots に max-image-preview:large を出す・公式の写真がある記事はシェア画像（og:image）を文字の無い写真にする。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const root = path.join(__dirname, '..');
// lib の相対の import（'./thumb-url'）も TypeScript のまま読む
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

test('[W32] サイト全体の robots に max-image-preview:large（googlebot だけでなく robots にも）', () => {
  const layout = read('app/layout.tsx');
  const robots = layout.slice(layout.indexOf('robots: {'), layout.indexOf('googleBot:'));
  assert.match(robots, /"max-image-preview": "large"/);
  assert.match(layout, /googleBot: \{[^}]*"max-image-preview": "large"/);
});

test('[W32] 公式の写真がある記事は、写真を og:image の先頭に（文字入りのカバーは2つ目）', () => {
  const { shareImages, hasOfficialPhoto } = load('lib/share-image.ts');
  const photo = 'https://ai-tech-express.jp/img/apple-health-1a2b3c4d.jpg';
  const official = { thumbnail: photo, imageCredit: { kind: 'official' } };
  assert.equal(hasOfficialPhoto(official), true);
  const images = shareImages(official, '/cover/apple-health?v=1', '題名');
  assert.equal(images[0].url, photo);
  assert.equal(images[0].width, 1200);
  assert.equal(images[1].url, '/cover/apple-health?v=1');
});

test('[W32] AI の絵・フリー素材・外部の画像の記事は、これまでどおり見出し入りのカバーが先', () => {
  const { shareImages } = load('lib/share-image.ts');
  const ai = { thumbnail: 'https://ai-tech-express.jp/img/yucho-1.jpg', imageCredit: { kind: 'ai' } };
  assert.equal(shareImages(ai, '/cover/yucho?v=1', '題名')[0].url, '/cover/yucho?v=1');
  const external = { thumbnail: 'https://i.ytimg.com/vi/x/maxresdefault.jpg', imageCredit: { kind: 'official' } };
  assert.equal(shareImages(external, '/cover/x?v=1', '題名')[0].url, '/cover/x?v=1');
  assert.equal(shareImages({ thumbnail: 'https://i.ytimg.com/vi/x/maxresdefault.jpg' }, undefined, '題名')[0].width, 1280);
});

test('[W32] 記事ページの og:image と X のカードは同じ順番の関数を使う', () => {
  const page = read('app/articles/[slug]/page.tsx');
  assert.match(page, /images: shareImages\(article, cover, title\),/);
  assert.match(page, /images: shareImages\(article, cover, title\)\.map/);
});

test('[A15] 公式の写真は本当の幅・高さを書く（1,200px 未満の写真に 1200 と書かない）', () => {
  const { shareImages } = load('lib/share-image.ts');
  const photo = 'https://ai-tech-express.jp/img/kao-1a2b3c4d.jpg';
  const small = shareImages({ thumbnail: photo, imageCredit: { kind: 'official', width: 800, height: 450 } }, '/cover/kao?v=1', '題名');
  assert.equal(small[0].width, 800);
  assert.equal(small[0].height, 450);
  const big = shareImages({ thumbnail: photo, imageCredit: { kind: 'official', width: 1200, height: 675 } }, '/cover/kao?v=1', '題名');
  assert.deepEqual([big[0].width, big[0].height], [1200, 675]);
});

test('[A15] トップ・ガイド・行事・製品・選び方・一覧のページに og:image（1200×630）', () => {
  const layout = read('app/layout.tsx');
  assert.match(layout, /images: \[\{ url: "\/og\/hub", width: 1200, height: 630/);
  assert.match(read('app/page.tsx'), /pageShareImage\("home"\)/);
  assert.match(read('app/guides/[slug]/page.tsx'), /withItemImage\(\{[\s\S]*?"guide", howto\.slug/);
  assert.match(read('app/events/[slug]/page.tsx'), /"event", event\.slug/);
  assert.match(read('app/events/page.tsx'), /pageShareImage\("events"\)/);
  assert.match(read('app/choose/[slug]/page.tsx'), /"choose", guide\.slug/);
  assert.match(read('app/choose/page.tsx'), /pageShareImage\("choose"\)/);
  assert.match(read('app/products/[slug]/page.tsx'), /itemShareImage\("product", product\.slug/);
  assert.match(read('app/articles/view.tsx'), /pageShareMetadata\("articles"/);
  assert.match(read('app/people/page.tsx'), /withPageShare\("people"/);
  assert.match(read('app/roundups/page.tsx'), /withPageShare\("roundups"/);
  // 画像はビルド時に描く（Workers で任意の題名を描かない）
  const route = read('app/og/[key]/route.tsx');
  assert.match(route, /dynamic = "force-static"/);
  assert.match(route, /dynamicParams = false/);
  assert.match(route, /allShareKeys\(\)/);
});

test('[A15] ガイドの題名は「？」「：」で見出しと下の行に分け、かっこの中や英語の空白では分けない', () => {
  const ts2 = require('typescript');
  const src = ts2.transpileModule(read('lib/page-share-items.ts'), { compilerOptions: { target: ts2.ScriptTarget.ES2022, module: ts2.ModuleKind.CommonJS } }).outputText;
  const m = new Module(path.join(root, 'lib/page-share-items.ts'), module);
  m.paths = module.paths;
  const stub = new Proxy({}, { get: () => () => undefined });
  m.require = (id) => (id.startsWith('@/') ? stub : require(id));
  m._compile(src, m.id);
  const { splitTitle } = m.exports;
  assert.deepEqual(splitTitle('児童手当はいくら？月1万円・1万5千円、高校生年代まで'), { heading: '児童手当はいくら？', rest: '月1万円・1万5千円、高校生年代まで' });
  assert.deepEqual(splitTitle('ChatGPTで画像生成するやり方：無料版で何枚まで作れるか、公式ページで確認'), { heading: 'ChatGPTで画像生成するやり方', rest: '無料版で何枚まで作れるか、公式ページで確認' });
  assert.equal(splitTitle('NotebookLM（Gemini Notebook）の使い方は？無料の上限と料金の違いもやさしく解説').rest, '');
  assert.deepEqual(splitTitle('短い題名'), { heading: '短い題名', rest: '' });
});
