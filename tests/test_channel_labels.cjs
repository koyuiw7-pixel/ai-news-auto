// SEO A11（2026-11-10）: 発信元ページの名前は組織の名前の表（content/channel_labels.json）から。
// 検索に出す発信元ページは「表に名前がある」かつ「検索に出す記事が3本以上」（ジャンルは問わない）。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');
const table = JSON.parse(read('content/channel_labels.json'));

test('[A11] 表の名前に資料名・日付・「」・縦棒が無い', () => {
  for (const [slug, label] of Object.entries(table.labels)) {
    assert.ok(label.trim().length > 0, slug);
    assert.doesNotMatch(label, /[「」｜]/, `${slug}: ${label}`);
    assert.doesNotMatch(label, /20\d\d年|令和\d+年|\d+月\d+日|確認）/, `${slug}: ${label}`);
    assert.ok(label.length <= 32, `${slug}: ${label}`);
  }
});

test('[A11] 暮らしとお金の主な発信元は組織の名前', () => {
  const want = { 'mhlw-go-jp': '厚生労働省', 'nta-go-jp': '国税庁', 'nenkin-go-jp': '日本年金機構', 'cfa-go-jp': 'こども家庭庁', 'docomo-ne-jp': 'NTTドコモ', mof: '財務省', 'tokyo-metro': '東京都' };
  for (const [slug, label] of Object.entries(want)) assert.equal(table.labels[slug], label, slug);
  // まとめるのは厚生労働省の2つだけ
  assert.deepEqual(table.aliases, { mhlw: 'mhlw-go-jp' });
});

test('[A11] 各社が混ざる配信・報道・話題のまとめは表に載せない（検索に出さない）', () => {
  for (const slug of ['fast', 'radar-official', 'trends', 'prtimes', 'prtimes-all', 'atpress', 'value-press', 'kyodo-prwire', 'dreamnews']) {
    assert.equal(table.labels[slug], undefined, slug);
  }
  for (const slug of Object.keys(table.labels)) assert.doesNotMatch(slug, /^radar-/);
});

test('[A11] 検索の扱いはページとサイトマップで同じ規則（AI の記事の有無ではなく、表の名前）', () => {
  const view = read('app/channels/[channel]/view.tsx');
  assert.match(view, /!isThinSourceChannel\(channel\) && hasChannelLabel\(channel\) && isListingIndexable\(items, path\)/);
  assert.match(view, /!isVideoListing\(items\) \|\| isProtectedListing\(path\)/);
  assert.doesNotMatch(view, /genreSlug === "ai"/);
  const sitemap = read('lib/sitemap.ts');
  assert.match(sitemap, /hasChannelLabel\(channel\.slug\)\s*&& isListingIndexable\(getArticlesByChannel\(channel\.slug\), `\/channels\/\$\{channel\.slug\}`\)/);
  assert.match(sitemap, /!isVideoListing\(getArticlesByChannel\(channel\.slug\)\) \|\| isProtectedListing\(`\/channels\/\$\{channel\.slug\}`\)/);
  assert.doesNotMatch(sitemap, /aiChannels/);
  // 名前は表から（h1・パンくず・足元）
  assert.match(read('lib/articles.ts'), /label: channelName\(slug, article\.channel\)/);
  assert.match(read('app/articles/[slug]/page.tsx'), /label: channelName\(article\.channelSlug, article\.channel\)/);
  // まとめた slug は転送
  assert.match(view, /permanentRedirect\(pageHref\(`\/channels\/\$\{canonicalChannel\(channel\)\}`/);
});
