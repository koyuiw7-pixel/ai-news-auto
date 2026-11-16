const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { marked } = require("marked");
const ts = require("typescript");
const Module = require("node:module");
function load(rel) {
  const file = path.resolve(__dirname, "..", rel);
  const out = ts.transpileModule(fs.readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const m = new Module(file, module);
  m.filename = file;
  m.paths = Module._nodeModulePaths(path.dirname(file));
  m._compile(out, file);
  return m.exports;
}
const { protectMaskStars } = load("lib/mask-stars.ts");

// 画面の崩れの点検（scripts/ui_check.mjs）の誤検知（2026-11-16 issue #155）
// ①品番の伏せ字「C05-*****-******1」を「生の **太字**」と数えない ②閉じた開け閉めの欄の中の箱を「空の箱」と数えない
const src = fs.readFileSync(path.resolve(__dirname, "..", "scripts/ui_check.mjs"), "utf8");
const line = src.split("\n").find((l) => l.includes('"生の **太字**"],'));
assert.ok(line, "生の太字の決まりが見つからない");
const RAW_BOLD = eval(line.trim().slice(1, line.trim().lastIndexOf(', "生の')));
const CELL = "C05で始まる全品番（表記 C05-*****-******1）";

test("伏せ字の「*」の並びは生の太字と数えない", () => {
  assert.equal(RAW_BOLD.test(CELL), false);
  for (const t of ["型番 AB-***-**1", "****", "*****-******"]) assert.equal(RAW_BOLD.test(t), false, t);
});

test("本当の生の太字は今までどおり見つける", () => {
  for (const t of ["月**30,000円**です", "**対象の条件**", "これは ** です", `**${"あ".repeat(10)}**`]) assert.equal(RAW_BOLD.test(t), true, t);
});

test("表のセルの伏せ字はそのまま出て、太字は太字になる", () => {
  const html = marked.parse(protectMaskStars(`| 確かめる場所 | 対象の条件 |\n|---|---|\n| 品番 | ${CELL} |\n| 品番 | **${CELL}** |\n`), { gfm: true });
  assert.ok(html.includes(`<td>${CELL}</td>`), html);
  assert.ok(html.includes(`<td><strong>${CELL}</strong></td>`), html);
});

test("ふつうの太字・斜体・区切り線は変えない", () => {
  for (const t of ["月**30,000円**です", "***強調***", "***", "- **A**-**B**", "a * b * c"]) assert.equal(protectMaskStars(t), t, t);
  assert.match(fs.readFileSync(path.resolve(__dirname, "..", "lib/markdown.ts"), "utf8"), /marked\.parse\(protectMaskStars\(tidy\)\)/);
});

test("閉じた開け閉めの欄の中は空の箱と数えない", () => {
  assert.match(src, /if \(!vis\(el\) \|\| el\.closest\("details:not\(\[open\]\)"\)\) continue;/);
});
