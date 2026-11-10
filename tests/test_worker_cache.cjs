const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// エッジのキャッシュの決まり（cloudflare/edge-cache.ts。seo A1・2026-11-10）
const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "cloudflare/edge-cache.ts");
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText;
const loaded = new Module(sourcePath, module);
loaded.filename = sourcePath;
loaded.paths = Module._nodeModulePaths(root);
loaded._compile(compiled, sourcePath);
const { edgeHitDecision, edgeCacheKeyUrl, mustBeCurrent } = loaded.exports;

const BASE = "https://ai-tech-express.jp";
const key = (p) => edgeCacheKeyUrl(new URL(BASE + p), "abc123");

test("前の版の写し: トップ・一覧・サイトマップ・フィードは返さず描き直す", () => {
  for (const p of ["/", "/news", "/news/", "/articles", "/sitemap.xml", "/sitemaps/articles-1.xml", "/news-sitemap.xml", "/feed.xml", "/feeds/smartnews.xml", "/feeds/news.xml"]) {
    assert.equal(mustBeCurrent(p), true, p);
    assert.equal(edgeHitDecision(p, "old", "new"), "render", p);
  }
});

test("前の版の写し: 記事ページなどは今までどおり古い版を返して裏で作り直す", () => {
  for (const p of ["/articles/some-slug", "/products/chatgpt", "/guides/x", "/articles/page/2", "/about"]) {
    assert.equal(mustBeCurrent(p), false, p);
    assert.equal(edgeHitDecision(p, "old", "new"), "stale", p);
  }
});

test("今の版の写し・版に関係しない画像はそのまま返す", () => {
  assert.equal(edgeHitDecision("/", "new", "new"), "fresh");
  assert.equal(edgeHitDecision("/sitemap.xml", "new", "new"), "fresh");
  assert.equal(edgeHitDecision("/articles/x", "new", "new"), "fresh");
  assert.equal(edgeHitDecision("/cover/x", "old", "new", true), "fresh");
  // 版の印が無い写しは古いものとして扱う
  assert.equal(edgeHitDecision("/", null, "new"), "render");
  assert.equal(edgeHitDecision("/articles/x", null, "new"), "stale");
});

test("計測用のパラメータは外し、何も付かない URL と同じキーにする", () => {
  const bare = key("/");
  assert.equal(bare, `${BASE}/?__c=abc123`);
  for (const q of ["igshid=abc", "ref=x", "s=1", "t=2", "msclkid=m", "yclid=y", "twclid=t", "ttclid=t", "_gl=1*abc", "srsltid=AfmB", "mc_cid=c", "fbclid=f", "gclid=g", "utm_source=threads&utm_medium=social"]) {
    assert.equal(key(`/?${q}`), bare, q);
  }
  assert.equal(key("/articles/x?igshid=abc&ref=x"), key("/articles/x"));
  assert.equal(key("/search?q=年金"), key("/search"));
});

test("ページを変えるパラメータは残す（別のキーになる）", () => {
  const bare = key("/");
  assert.notEqual(key("/?v=123"), bare);
  assert.notEqual(key("/?_cold=999"), bare);
  assert.notEqual(key("/?_cold=1"), key("/?_cold=2"));
  assert.notEqual(key("/?_internal=1"), bare);
  assert.notEqual(key("/article-concept?slug=a"), key("/article-concept?slug=b"));
  assert.notEqual(key("/?design=b"), bare);
  assert.notEqual(key("/card/x?v=1"), key("/card/x?v=2"));
  assert.equal(key("/?v=123&igshid=z"), key("/?v=123"));
});

test("メールの登録・解除のページでは ?s= ?t= を残す", () => {
  assert.notEqual(key("/newsletter?s=confirmed"), key("/newsletter"));
  assert.notEqual(key("/newsletter/unsubscribe?id=1&t=tok"), key("/newsletter/unsubscribe?id=1"));
});
