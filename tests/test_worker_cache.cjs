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
const { edgeHitDecision, edgeCacheKeyUrl, mustBeCurrent, isInternalRequest } = loaded.exports;

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

// Worker の内訳（Server-Timing）は自社の確かめのときだけ返し、エッジのキャッシュには残さない（台帳 W43。2026-11-13）
test("内訳: 自社の確かめ（ヘッダーか ?_internal=1）だけ", () => {
  const h = (v) => ({ get: (n) => (n === "x-saisoku-internal" ? v : null) });
  assert.equal(isInternalRequest(h("1"), new URL(BASE + "/articles/x")), true);
  assert.equal(isInternalRequest(h(null), new URL(BASE + "/articles/x?_internal=1")), true);
  assert.equal(isInternalRequest(h(null), new URL(BASE + "/articles/x")), false);
  assert.equal(isInternalRequest(h("0"), new URL(BASE + "/articles/x?_internal=0")), false);
});

test("内訳: render が付けた Server-Timing は forEdge で外し、エッジに置かない", () => {
  const worker = fs.readFileSync(path.join(root, "cloudflare/worker.ts"), "utf8");
  const forEdge = worker.slice(worker.indexOf("function forEdge("), worker.indexOf("type KvNamespace"));
  assert.match(forEdge, /headers\.delete\("server-timing"\)/);
  const render = worker.slice(worker.indexOf("async function render("), worker.indexOf("export default {"));
  assert.match(render, /if \(!isInternalRequest\(request\.headers, url\)\) return response;/);
  assert.match(render, /return withTiming\(response/);
});

// 記事ページは、ビルドで作ったページ（ISR のキャッシュ）を返すだけなら記事 JSON の読み込みを待たない。
// キャッシュに無くて描くときだけ、open-next.config.ts の kvOverAssets.get が読み込みの終わりを待つ（台帳 W43。2026-11-13）
test("記事ページ: 記事 JSON を待たずに Next へ渡し、キャッシュに無いときだけ待つ", () => {
  const worker = fs.readFileSync(path.join(root, "cloudflare/worker.ts"), "utf8");
  const render = worker.slice(worker.indexOf("async function render("), worker.indexOf("export default {"));
  const handOff = render.indexOf("handler.fetch(request, env, ctx)");
  assert.ok(handOff > 0);
  // 記事ページの読み込みは trackContent に入れるだけで、Next へ渡す前に await しない
  assert.match(render, /articleLoad = trackContent\(loadArticle\(env, articleSlug\)\)/);
  assert.doesNotMatch(render.slice(0, handOff), /await articleLoad/);
  // 読めなかったときは描いたページを 503 に、先に描いて 404 になったら描き直す
  assert.match(render.slice(handOff), /await articleLoad/);
  assert.match(render.slice(handOff), /status: 503/);
  assert.match(render.slice(handOff), /exists && response\.status === 404/);
  assert.match(worker, /__SAISOKU_CONTENT_PENDING__ = pendingContent/);

  const config = fs.readFileSync(path.join(root, "open-next.config.ts"), "utf8");
  assert.match(config, /__SAISOKU_CONTENT_PENDING__/);
  const get = config.slice(config.indexOf("async get(key, cacheType)"), config.indexOf("set: async"));
  assert.match(get, /if \(!fromKv\?\.value\) await contentReady\(\)/);
  // 一時的な 404 を ISR に残さない
  const set = config.slice(config.indexOf("set: async"), config.indexOf("delete:"));
  assert.match(set, /if \(isNotFoundEntry\(value\)\) return;/);
});
