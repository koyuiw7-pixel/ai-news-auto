const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

// 手で事実を足した記事は、更新履歴の行が無くても「最終更新」を出す（lib/article-index.mjs の trustedUpdatedAt。2026-11-13 オーナー「Googleからの流入対策をもっと」）
const root = path.resolve(__dirname, "..");
const load = () => import(path.join(root, "lib/article-index.mjs"));

test("履歴が無くても、11/13 以降で載せた時刻より10分を超えて新しい updatedAt は使う", async () => {
  const { trustedUpdatedAt } = await load();
  const born = "2026-11-13T04:38:33+00:00";
  assert.equal(trustedUpdatedAt({ generatedAt: born, updatedAt: "2026-11-13T05:38:44+00:00" }), "2026-11-13T05:38:44+00:00");
  // 10分以内は公開の準備の一部
  assert.equal(trustedUpdatedAt({ generatedAt: born, updatedAt: "2026-11-13T04:48:33+00:00" }), undefined);
  assert.equal(trustedUpdatedAt({ generatedAt: born, updatedAt: "2026-11-13T04:48:34+00:00" }), "2026-11-13T04:48:34+00:00");
  // generatedAt が無ければ publishedAt と比べる。どちらも無ければ使わない
  assert.equal(trustedUpdatedAt({ publishedAt: born, updatedAt: "2026-11-13T06:00:00+00:00" }), "2026-11-13T06:00:00+00:00");
  assert.equal(trustedUpdatedAt({ updatedAt: "2026-11-13T06:00:00+00:00" }), undefined);
});

test("11/12 までの履歴の無い updatedAt（一括で押された日時）は今までどおり使わない。履歴・書き直しの印があれば使う", async () => {
  const { trustedUpdatedAt } = await load();
  assert.equal(trustedUpdatedAt({ generatedAt: "2026-10-20T00:00:00Z", updatedAt: "2026-11-04T01:17:57+00:00" }), undefined);
  assert.equal(trustedUpdatedAt({ generatedAt: "2026-10-20T00:00:00Z", updatedAt: "2026-11-12T14:59:59+00:00" }), undefined);
  assert.equal(trustedUpdatedAt({ generatedAt: "2026-10-20T00:00:00Z", updatedAt: "2026-11-04T01:17:57+00:00", updates: [{ at: "x" }] }), "2026-11-04T01:17:57+00:00");
  assert.equal(trustedUpdatedAt({ generatedAt: "2026-10-20T00:00:00Z", updatedAt: "2026-11-04T01:17:57+00:00", searchRefreshedAt: "x" }), "2026-11-04T01:17:57+00:00");
  assert.equal(trustedUpdatedAt({ generatedAt: "2026-10-20T00:00:00Z" }), undefined);
});

test("紅白の出場歌手の一覧: 41組の表を足した時刻が最終更新になる。今ある記事で新しく更新扱いになるのは 11/13 以降に手で直した記事だけ", async () => {
  const { trustedUpdatedAt, UPDATED_AT_ALONE_FROM } = await load();
  const dir = path.join(root, "content/articles");
  const kohaku = JSON.parse(fs.readFileSync(path.join(dir, "nhk-kohaku-2026-41-performers.json"), "utf8"));
  const at = trustedUpdatedAt(kohaku);
  assert.ok(at && Date.parse(at) > Date.parse(kohaku.generatedAt), "紅白の一覧の dateModified は datePublished より後");
  for (const name of fs.readdirSync(dir).filter((n) => n.endsWith(".json"))) {
    const a = JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
    if (!a.updatedAt || (a.updates ?? []).length > 0 || a.searchRefreshedAt) continue;
    if (Date.parse(a.updatedAt) < UPDATED_AT_ALONE_FROM) assert.equal(trustedUpdatedAt(a), undefined, name);
  }
});

test("最終更新の出し先（構造化データ・article:modified_time・画面の「更新」・サイトマップ）はどれも同じ updatedAt を使う", () => {
  const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
  assert.match(read("lib/article-index.mjs"), /updatedAt: trustedUpdatedAt\(parsed\)/);
  const page = read("app/articles/[slug]/page.tsx");
  assert.match(page, /modifiedTime: lastModifiedOf\(article\)/);
  assert.match(page, /dateModified: lastModifiedOf\(article\)/);
  assert.match(read("lib/sitemap.ts"), /lastModified: toDate\(lastModifiedOf\(article\)\)/);
  assert.match(read("lib/articles.ts"), /return article\.updatedAt \|\| article\.generatedAt \|\| article\.publishedAt;/);
});
