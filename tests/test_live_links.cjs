const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 取り下げた・無い記事へのリンクを画面に出さない（lib/live-links.ts。台帳 A9）
const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib/live-links.ts");
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText;
const loaded = new Module(sourcePath, module);
loaded.filename = sourcePath;
loaded.paths = Module._nodeModulePaths(root);
loaded._compile(compiled, sourcePath);
const { dropDeadArticleLinks, withLiveRoundup } = loaded.exports;

const retired = new Set(Object.keys(JSON.parse(fs.readFileSync(path.join(root, "content/retired.json"), "utf8")).articles ?? {}));
const isLive = (slug) => !retired.has(slug) && fs.existsSync(path.join(root, "content/articles", `${slug}.json`));
const retiredSlug = "gyakuhibu-cross-trade-complete-guide-matome";

test("まとめ記事（roundupSlug）が取り下げ済みなら、まとめの案内を出さない", () => {
  assert.ok(retired.has(retiredSlug), "テストの前提: このまとめは取り下げ済み");
  const out = withLiveRoundup({ slug: "a", roundupSlug: retiredSlug, roundupTitle: "まとめ" }, isLive);
  assert.equal(out.roundupSlug, undefined);
  assert.equal(out.roundupTitle, undefined);
  assert.equal(out.slug, "a");
});

test("まとめ記事が無い（ファイルが無い）ときも出さない。生きていればそのまま", () => {
  assert.equal(withLiveRoundup({ roundupSlug: "no-such-article-xyz", roundupTitle: "t" }, isLive).roundupSlug, undefined);
  const article = { roundupSlug: "live-one", roundupTitle: "t" };
  assert.equal(withLiveRoundup(article, () => true), article);
});

test("本文の取り下げ済み・無い記事へのリンクは外し、文字は残す", () => {
  const html =
    `<p>詳しくは<a href="/articles/${retiredSlug}">つなぎ売りのまとめ</a>へ。` +
    `<a href="https://ai-tech-express.jp/articles/${retiredSlug}#faq">絶対URL</a>、` +
    `<a href="/articles/live-one">生きている記事</a>。</p>`;
  const out = dropDeadArticleLinks(html, (s) => s === "live-one");
  assert.equal(out, `<p>詳しくはつなぎ売りのまとめへ。絶対URL、<a href="/articles/live-one">生きている記事</a>。</p>`);
});

test("リンクの文字が slug や「関連記事」なら、（）ごと外す", () => {
  const out = dropDeadArticleLinks(
    `<li>GビズIDの更新（<a href="/articles/gone-x">gone-x</a>）と（<a href="/articles/gone-y">関連記事</a>）</li>`,
    () => false,
  );
  assert.equal(out, "<li>GビズIDの更新と</li>");
});

test("外のサイトの /articles/ のリンクには触らない", () => {
  const html = `<a href="https://example.com/articles/gone-x" target="_blank" rel="noopener noreferrer nofollow">外</a>`;
  assert.equal(dropDeadArticleLinks(html, () => false), html);
});
