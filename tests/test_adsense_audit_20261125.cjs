// 2026-11-25 AdSense の申請の前の点検（30ページ）で見つかった、サイト全体の問題の直し。
// 1. 記事ページの HTML に要約版と詳細版の両方を入れない（要約版は読者が選んだときに /api/easy から読み込む）
// 2・3. 報道が出典の記事（press）・動画だけから作った記事（video-only）は検索に出さない（記事は消さない）
// 4. 足もとの「TOPICS」（AI の話題のタグ）を全ページに出さない
// 5. 重複の URL（claude-meetings-beta）は代表の記事へ 301
// 6. 研究・デモ段階の記事に「日本でも提供予定」と出さない・社内の事例に判定欄を出さない
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const Module = require("node:module");

const root = path.join(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(root, f), "utf8");

function load(rel) {
  const filename = path.join(root, rel);
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
  const m = new Module(filename, module);
  m.filename = filename;
  m.paths = module.paths;
  m._compile(compiled, filename);
  return m.exports;
}

test("記事ページの HTML には要約版の本文を入れず、読者が選んだときに読み込む", () => {
  const page = read("app/articles/[slug]/page.tsx");
  const noir = read("components/noir/noirArticlePage.tsx");
  for (const src of [page, noir]) {
    assert.doesNotMatch(src, /__html: (?:noirBodyHtml\()?easyHtml/, "要約版の HTML をページに入れている");
    assert.match(src, /data-easy-body=""/);
    assert.match(src, /<ReadingMode slug=\{article\.slug\}/);
  }
  const mode = read("components/ReadingMode.tsx");
  assert.match(mode, /fetch\(`\/api\/easy\/\$\{encodeURIComponent\(slug\)\}/);
  assert.match(mode, /\[data-easy-body\]/);
  assert.match(mode, /noir \? "\/noir" : ""/);
  // 要約版はビルド時に静的に作る（2026-11-26: 実行時に描く作りでは Cloudflare で記事 JSON が読めず本番で 404 だった）
  const api = read("lib/easy-api.ts");
  assert.match(api, /easyHtmlOf\(article, noir\)/);
  assert.match(api, /"X-Robots-Tag": "noindex/);
  for (const [file, noir] of [["app/api/easy/[slug]/route.ts", "false"], ["app/api/easy/[slug]/noir/route.ts", "true"]]) {
    const route = read(file);
    assert.match(route, /export const dynamic = "force-static"/, file);
    assert.doesNotMatch(route, /force-dynamic/, file);
    assert.match(route, new RegExp(`easyStaticParams\\(${noir}\\)`), file);
    assert.match(route, new RegExp(`easyResponse\\(slug, ${noir}\\)`), file);
  }
  // ビルドに無い slug を描くときのため、Worker は /api/easy/<slug> でも記事 JSON を先読みする
  assert.match(read("cloudflare/worker.ts"), /const ARTICLE = .*api\\\/easy/);
  // /api/ は巡回させない
  assert.match(read("app/robots.ts"), /BLOCKED_PATHS = \["\/api\/"/);
  // 本番のサーバー関数に記事の JSON を同梱する
  assert.match(read("next.config.ts"), /"\/api\/easy\/\\\\\[slug\\\\\]": \["\.\/content\/articles\/\*\*\/\*\.json"\]/);
  assert.match(read("next.config.ts"), /"\/api\/easy\/\\\\\[slug\\\\\]\/noir": \["\.\/content\/articles\/\*\*\/\*\.json"\]/);
});

test("報道が出典の記事と動画だけの記事は検索に出さない（理由 press・video-only）", () => {
  const { noindexReason, isPressSourced, isVideoOnly, isPressHost } = load("lib/indexing.ts");
  const good = { slug: "a", sourceType: "web", channelSlug: "mhlw", genreSlug: "public", title: "x", tags: [], bodyLength: 2000, bodyChars: 2000,
    hasJapanValue: true, sourceUrl: "https://www.mhlw.go.jp/a.html", videoId: "" };
  assert.equal(noindexReason(good), null);
  for (const url of ["https://topics.smt.docomo.ne.jp/article/x", "https://news.yahoo.co.jp/articles/1", "https://news.web.nhk/x", "https://www.nikkei.com/a",
    "https://newsdig.tbs.co.jp/a", "https://www.yomiuri.co.jp/a"]) {
    assert.equal(isPressHost(url), true, url);
    assert.equal(noindexReason({ ...good, sourceUrl: url }), "press", url);
  }
  for (const url of ["https://www.docomo.ne.jp/info/1", "https://www.nhk.or.jp/info/1", "", "x"]) assert.equal(isPressHost(url), false, url);
  assert.equal(noindexReason({ ...good, pressOnly: true }), "press");
  assert.equal(noindexReason({ ...good, awaitingOfficial: true }), "press");
  assert.equal(noindexReason({ ...good, pressReport: true }), "press");
  assert.equal(isPressSourced({ ...good, pressReport: true, officialSourceUrl: "https://www.sony.jp/x" }), false);
  assert.equal(noindexReason({ ...good, channelSlug: "radar-itmedia.co.jp" }), "press");
  assert.equal(noindexReason({ ...good, channelSlug: "radar-official" }), null);
  assert.equal(noindexReason({ ...good, pressOnly: true, indexable: true }), null);
  const video = { ...good, sourceType: undefined, sourceUrl: undefined, videoId: "abc" };
  assert.equal(isVideoOnly(video), true);
  assert.equal(noindexReason(video), "video-only");
  assert.equal(noindexReason({ ...video, type: "roundup" }), null);
  assert.equal(noindexReason({ ...good, videoId: "abc" }), null);
});

test("報道の印は一覧用の索引（ArticleSummary）にも入る", () => {
  const src = read("lib/article-index.mjs");
  for (const key of ["pressReport", "awaitingOfficial", "pressOnly", "officialSourceUrl"]) assert.match(src, new RegExp(`${key}: a\\.${key}`), key);
});

test("足もとに AI の話題のタグの一覧（TOPICS）を出さない", () => {
  const footer = read("components/Footer.tsx");
  assert.doesNotMatch(footer, />TOPICS</);
  assert.doesNotMatch(footer, /getAllTags/);
});

test("重複の URL /articles/claude-meetings-beta は代表の記事へ転送する", () => {
  const retired = JSON.parse(read("content/retired.json")).articles;
  assert.equal(retired["claude-meetings-beta"].redirect, "claude-meetings-google-meet-beta");
  assert.equal(fs.existsSync(path.join(root, "content/articles/claude-meetings-beta.json")), false);
  assert.equal(fs.existsSync(path.join(root, "content/articles/claude-meetings-google-meet-beta.json")), true);
});

test("研究・デモ段階に「日本でも提供予定」と出さない・社内の事例には判定欄を出さない", () => {
  const { japanLabel, verdictOf } = load("lib/verdict.ts");
  const v = (status, japan, take = "") => ({ status, japan, price: "", free: null, audience: "", take });
  assert.equal(japanLabel(v("demo", "ok")), "提供の予定は未発表");
  assert.equal(japanLabel(v("demo", "partial")), "提供の予定は未発表");
  assert.equal(japanLabel(v("soon", "ok")), "日本でも提供予定");
  const article = JSON.parse(read("content/articles/openai-frontier-model-misalignment-monitoring.json"));
  assert.equal(verdictOf(article), undefined);
});

test("訂正履歴に6本の直しを載せる", () => {
  const list = JSON.parse(read("content/corrections.json"));
  for (const slug of ["mlit-autumn-2026-medals-of-honor", "starbucks-fukubukuro-2027-lottery-result", "nicorio-flavos-refund-process",
    "kogaku-ryoyohi-2026-08-limit", "docomo-data-leak-what-to-do", "openai-frontier-model-misalignment-monitoring"]) {
    assert.ok(list.some((c) => c.slug === slug && c.date === "2026-11-25"), slug);
  }
  for (const c of list) assert.doesNotMatch(c.summary, /｜|ざっくり/);
});
