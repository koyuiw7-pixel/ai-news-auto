const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");
const { marked } = require("marked");

// 記号のそばの「**…**」も太字にする（lib/leftover-bold.ts。2026-11-27 生の ** が本番で見えた）
const root = path.resolve(__dirname, "..");
function load(rel) {
  const sourcePath = path.join(root, rel);
  const compiled = ts.transpileModule(fs.readFileSync(sourcePath, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const loaded = new Module(sourcePath, module);
  loaded.filename = sourcePath;
  loaded.paths = Module._nodeModulePaths(root);
  loaded._compile(compiled, sourcePath);
  return loaded.exports;
}
const { boldToHtml } = load("lib/leftover-bold.ts");
const { protectMaskStars } = load("lib/mask-stars.ts");
marked.setOptions({ gfm: true, breaks: false });
const render = (md) => marked.parse(protectMaskStars(boldToHtml(md)));
const visible = (html) => html.replace(/<pre[\s\S]*?<\/pre>|<code[\s\S]*?<\/code>/g, "").replace(/<[^>]+>/g, "");

test("かっこで終わる太字も太字になり、生の ** が残らない", () => {
  for (const md of [
    "繰り返し訴えているのは、**「ハードウェアに依存しない汎用的なAI頭脳」**としての役割です。",
    "利用料金は**完全に無料（0円）**です。",
    "スタートアップの**Clio（クリオ）**は、文書を解析します。",
    "環境である**「OpenShell」**の土台を築き、設計図**「Secure Agent Workspace」**を公開しました。",
  ]) {
    const html = render(md);
    assert.match(html, /<strong>[^<]+<\/strong>/, md);
    assert.doesNotMatch(visible(html), /\*\*/, md);
  }
});

test("ふつうの太字・伏せ字・コードはそのまま", () => {
  assert.equal(render("1リットル**175円**となります。").trim(), "<p>1リットル<strong>175円</strong>となります。</p>");
  assert.match(render("品番 C05-*****-******1 が対象"), /C05-\*{5}-\*{6}1/);
  assert.match(render("`a**b**c` と書く"), /<code>a\*\*b\*\*c<\/code>/);
});
