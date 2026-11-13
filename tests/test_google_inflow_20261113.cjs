const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

// 2026-11-13 の Google 流入の点検で直したひな形の決まり（題名が同じ一覧・記事ページの RSS の案内）
const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

test("ジャンルと同じ名前のタグの一覧は検索に出さず、canonical をジャンルの一覧へ向ける。サイトマップにも載せない", () => {
  const view = read("app/tags/[tag]/view.tsx");
  assert.match(view, /const twin = genreTwinOfTag\(tag\)/);
  assert.match(view, /canonical: twin \? pageHref\(`\/genres\/\$\{twin\}`, 1\)/);
  assert.match(view, /twin \? \{ robots: \{ index: false, follow: true \} \}/);
  assert.match(read("lib/sitemap.ts"), /!genreTwinOfTag\(tag\.slug\)/);
  assert.match(read("lib/articles.ts"), /export function genreTwinOfTag\(tag: string\): string \| null/);
});

test("記事ページの head に RSS の場所を書く（ページごとの alternates は layout の指定を引き継がない）", () => {
  const page = read("app/articles/[slug]/page.tsx");
  const block = page.slice(page.indexOf("alternates: {"), page.indexOf("alternates: {") + 600);
  assert.match(block, /canonical: canonicalPathOf/);
  assert.match(block, /types: \{ "application\/rss\+xml": "\/feed\.xml" \}/);
});
