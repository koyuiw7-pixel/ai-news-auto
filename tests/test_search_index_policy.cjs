const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const filename = path.join(__dirname, '../lib/indexing.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true}}).outputText;
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded._compile(compiled, filename);
const { isIndexable, isDistributionEligible, noindexReason, focusReason, lifeLink, isListingIndexable, isVideoListing, canonicalPathOf, newsSitemapReason } = loaded.exports;

const good = { sourceType: 'web', channelSlug: 'official', genreSlug: 'ai', title: 'x', tags: [], bodyLength: 2000, hasJapanValue: true };

test('検索に出す条件（分量・主題・日本向けの情報・重複）', () => {
  assert.equal(focusReason(good), null);
  assert.equal(focusReason({ ...good, bodyLength: 1499 }), 'thin');
  assert.equal(focusReason({ ...good, genreSlug: 'entertainment', title: '新作ゲームの体験版' }), 'off-focus');
  assert.equal(focusReason({ ...good, genreSlug: 'public', title: '生成AIの指針' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'business', tags: ['AI'] }), null);
  assert.equal(focusReason({ ...good, hasJapanValue: false }), 'no-japan-value');
  assert.equal(focusReason({ ...good, hasJapanValue: false, verdict: { japan: 'ok' } }), null);
  assert.equal(focusReason({ ...good, duplicate: true }), 'duplicate');
  assert.equal(focusReason({ ...good, sourceType: 'video' }), null);
});

test('主題は読者像（scripts/persona.py）に合わせる: お金・制度・日本のスポーツは対象、エンタメ・海外スポーツは外す', () => {
  assert.equal(focusReason({ ...good, genreSlug: 'business', title: '財務省が10月の国債金利を公表' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'investment', title: '楽天証券の口座数' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'real-estate', title: '路線価' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'public', title: '国の教育ローン、世帯年収の上限と金利' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'public', title: '道路の工事', seoTitle: '補助金の申請' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'public', title: '道路の工事' }), 'off-focus');
  assert.equal(focusReason({ ...good, genreSlug: 'lifestyle', title: '新作ラテが期間限定で発売' }), 'off-focus');
  assert.equal(focusReason({ ...good, genreSlug: 'science', title: '天文台の教授が褒章' }), 'off-focus');
  assert.equal(focusReason({ ...good, genreSlug: 'sports', title: 'なでしこジャパンがブラジルと対戦' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'sports', title: '大谷翔平のドジャースが勝利' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'sports', title: 'レイカーズが開幕戦に勝利' }), 'off-focus');
  assert.equal(focusReason({ ...good, genreSlug: 'sports', title: '世界陸上でボルトの記録に迫る' }), null);
  assert.equal(focusReason({ ...good, genreSlug: 'sports', title: 'ＮＢＡのウォリアーズ' }), 'off-focus');
});

test('手動指定・配信元・まとめ記事の扱いと、既存の配信基準を保つ', () => {
  const short = { ...good, bodyLength: 20 };
  assert.equal(isIndexable({ ...good, indexable: false }), false);
  assert.equal(isIndexable({ ...short, indexable: true }), true);
  assert.equal(focusReason({ ...good, channelSlug: "prtimes" }), "wire");
  assert.equal(isIndexable({ ...good, channelSlug: "prtimes" }), true); // 2026-11-08 台帳 A61: 配信元でも検索に出す
  assert.equal(isIndexable({ ...short, type: 'roundup' }), true);
  assert.equal(isDistributionEligible(short), false);
  assert.equal(isDistributionEligible(good), true);
  assert.equal(isDistributionEligible({ ...short, type: 'roundup' }), true);
  assert.equal(isDistributionEligible({ ...short, sourceType: 'video' }), true);
  assert.equal(isDistributionEligible({ ...short, channelSlug: 'prtimes' }), false);
});

test('一覧ページは検索対象の記事が3本以上・公開の記事が5本以上で検索に出す（2026-11-12 AdSense 監査）', () => {
  assert.equal(isListingIndexable([good, good]), false);
  assert.equal(isListingIndexable([good, good, { ...good, bodyLength: 1 }]), false);
  assert.equal(isListingIndexable([good, good, good]), false);
  assert.equal(isListingIndexable([good, good, good, good, good]), true);
  assert.equal(isListingIndexable([good, good, good, { ...good, bodyLength: 1 }, { ...good, bodyLength: 1 }]), true);
});

test('読まれた一覧（content/list_pages_protected.json）は公開の記事が5本未満でも検索に出したまま', () => {
  assert.equal(isListingIndexable([good, good, good], '/tags/年金'), true);
  assert.equal(isListingIndexable([good, good, good], '/tags/%E5%B9%B4%E9%87%91'), true);
  assert.equal(isListingIndexable([good, good, good], '/tags/not-read'), false);
  assert.equal(isListingIndexable([good, good], '/tags/年金'), false);
});

test('YouTube の動画の要約が半分以上の一覧は動画の一覧', () => {
  const video = { ...good, sourceType: 'video', videoId: 'abc' };
  assert.equal(isVideoListing([video, video, good]), true);
  assert.equal(isVideoListing([video, good, good]), false);
  assert.equal(isVideoListing([]), false);
});

test('重複記事（duplicateOf）は noindex で canonical は代表へ', () => {
  assert.equal(noindexReason({ ...good, slug: 'b', duplicateOf: 'a' }), 'duplicate');
  assert.equal(noindexReason({ ...good, slug: 'a', duplicateOf: 'a' }), null);
  assert.equal(canonicalPathOf({ slug: 'b', duplicateOf: 'a' }), '/articles/a');
  assert.equal(canonicalPathOf({ slug: 'b' }), '/articles/b');
});

test('ニュース用サイトマップは元の発表から48時間以内・重複でない記事だけ（scripts/indexnow.py news_reason と同じ）', () => {
  const now = Date.parse('2026-11-02T12:00:00Z');
  const fresh = { ...good, slug: 'x', generatedAt: '2026-11-02T06:00:00Z', publishedAt: '2026-11-02T05:00:00Z' };
  assert.equal(newsSitemapReason(fresh, now), null);
  assert.equal(newsSitemapReason({ ...fresh, publishedAt: '2026-10-27T16:00:00Z' }, now), 'stale-source');
  assert.equal(newsSitemapReason({ ...fresh, sourcePublishedAt: '2026-10-29T00:00:00Z' }, now), 'stale-source');
  assert.equal(newsSitemapReason({ ...fresh, generatedAt: '2026-10-30T00:00:00Z' }, now), 'old');
  assert.equal(newsSitemapReason({ ...fresh, duplicateOf: 'y' }, now), 'duplicate');
  // 別の角度の解説は、載せて48時間以内なら載せる（2026-11-13）。古い発表から作った・遅れて作った解説は今までどおり載せない
  assert.equal(newsSitemapReason({ ...fresh, angleOf: 'y' }, now), null);
  assert.equal(newsSitemapReason({ ...fresh, angleOf: 'y', generatedAt: '2026-10-30T00:00:00Z' }, now), 'old');
  assert.equal(newsSitemapReason({ ...fresh, angleOf: 'y', sourcePublishedAt: '2026-10-29T00:00:00Z' }, now), 'stale-source');
  assert.equal(newsSitemapReason({ ...fresh, angleOf: 'y', late: true }, now), 'late');
  assert.equal(newsSitemapReason({ ...fresh, late: true }, now), 'late');
  assert.equal(newsSitemapReason({ ...fresh, type: 'roundup' }, now), 'roundup');
});

test('A43: ゲーム機・ゲームのサービスの公式の発表（本体・料金・セール）は主題。レビュー・報道・ソフトの告知は外す', () => {
  const game = { ...good, genreSlug: 'entertainment' };
  assert.equal(focusReason({ ...game, channelSlug: 'playstation-blog-jp', title: 'PS5 Proの価格を11月20日に改定' }), null);
  assert.equal(focusReason({ ...game, channelSlug: 'playstation-blog-jp', title: 'PlayStation Storeでブラックフライデーセールを開催' }), null);
  assert.equal(focusReason({ ...game, channelSlug: 'nintendo-topics', title: 'Nintendo Switch 2 本体の国内発売日が決定' }), null);
  assert.equal(focusReason({ ...game, channelSlug: 'nintendo-topics', title: '『新作RPG』レビュー：Switch 2で遊んでみた' }), 'off-focus');
  assert.equal(focusReason({ ...game, channelSlug: 'gamespark', title: 'PlayStation Storeでセールを開催' }), 'off-focus');
  assert.equal(focusReason({ ...game, channelSlug: 'nintendo-topics', title: '『新作RPG』本日発売' }), 'off-focus');
});

test('A10: 速報・お知らせ・注意喚起・ミサイル・災害は本文800字から検索に出す。ほかは1,500字のまま', () => {
  assert.equal(focusReason({ ...good, bodyLength: 900, breaking: true }), null);
  assert.equal(focusReason({ ...good, bodyLength: 900, newsType: 'breaking' }), null);
  assert.equal(focusReason({ ...good, bodyLength: 900, title: 'Microsoft 365で障害、Outlookがつながりにくい状態' }), null);
  assert.equal(focusReason({ ...good, bodyLength: 900, title: '国税庁を名乗るフィッシングメールに注意喚起' }), null);
  assert.equal(focusReason({ ...good, bodyLength: 799, breaking: true }), 'thin');
  assert.equal(focusReason({ ...good, bodyLength: 900 }), 'thin');
  assert.equal(focusReason({ ...good, bodyLength: 1499, title: 'iPhoneの新機能' }), 'thin');
  assert.equal(focusReason({ ...good, bodyLength: 900, genreSlug: 'public', title: '障害者手帳のアプリ' }), 'thin');
});

test('2026-11-08 台帳 A61: 検索に出さないのは重複・本文が無い記事だけ（2026-11-13 から題名の語では外さない。scripts/indexnow.py の noindex_reason と同じ）', () => {
  assert.equal(noindexReason({ ...good, bodyLength: 900 }), null);
  assert.equal(noindexReason({ ...good, bodyLength: 150 }), 'no-body');
  assert.equal(noindexReason({ ...good, hasJapanValue: false }), null);
  assert.equal(noindexReason({ ...good, genreSlug: 'lifestyle', title: '新作ラテが期間限定で発売' }), null);
  assert.equal(noindexReason({ ...good, genreSlug: 'lifestyle', title: '釣八の塩さばフィーレに原産地表示違反' }), null);
  assert.equal(noindexReason({ ...good, genreSlug: 'entertainment', title: 'ツイステの歌唱曲のスペシャルPV特設サイトが公開' }), null);
  assert.equal(noindexReason({ ...good, genreSlug: 'sports', title: 'レイカーズが開幕戦に勝利' }), null);
  assert.equal(noindexReason({ ...good, genreSlug: 'sports', title: 'レイカーズ戦のチケットを12月に発売' }), null);
  assert.equal(lifeLink('NBAの試合結果'), false);
  assert.equal(noindexReason({ ...good, duplicate: true }), 'duplicate');
});
