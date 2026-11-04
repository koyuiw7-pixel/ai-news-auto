const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 「この記事のポイント」などの番号つきの並びで「1. 1〜」と番号が二重にならない（2026-11-05 台帳 W34。
// アララの記事で、<ol> の番号に加えて文字の番号 <span>1</span> を置いていたため、文字だけを取り出す読み方で二重になっていた）
const root = path.resolve(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
function load(rel) {
  const file = path.join(root, rel);
  const out = ts.transpileModule(read(rel), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const m = new Module(file, module);
  m.filename = file;
  m.paths = Module._nodeModulePaths(path.dirname(file));
  m._compile(out, file);
  return m.exports;
}

test("要点の頭の番号は外す（小数・年は残す）", () => {
  const { stripListNumber } = load("lib/list-number.ts");
  assert.equal(stripListNumber("1. 約7,700万件が持ち出された恐れ"), "約7,700万件が持ち出された恐れ");
  assert.equal(stripListNumber("１．サーバー97台に拡大"), "サーバー97台に拡大");
  assert.equal(stripListNumber("(2) 再開は未定"), "再開は未定");
  assert.equal(stripListNumber("③ 第3報で示される予定"), "第3報で示される予定");
  assert.equal(stripListNumber("3.5GHz帯の電波を使う"), "3.5GHz帯の電波を使う");
  assert.equal(stripListNumber("2026年11月2日の第2報"), "2026年11月2日の第2報");
  assert.equal(stripListNumber("1."), "1.");
});

test("番号つきの並びは番号を CSS で1回だけ描く（文字の番号を足さない）", () => {
  const css = read("app/globals.css");
  assert.match(css, /\.num-list > li::before \{[^}]*content: counter\(num-list\)/);
  // Tailwind の before: の content に負けないよう、レイヤーの外に置く
  assert.match(css, /\n\.num-list \{/, "行の頭（どの @layer の中でもない）に置く");
  const pages = {
    "app/articles/[slug]/page.tsx": "article.highlights.map",
    "app/guides/[slug]/page.tsx": "guide.summary.map",
    "app/compare/[slug]/page.tsx": "guide.criteria.map",
  };
  for (const [file, marker] of Object.entries(pages)) {
    const src = read(file);
    const at = src.indexOf(marker);
    assert.ok(at > 0, `${file}: ${marker}`);
    const before = src.slice(Math.max(0, at - 400), at);
    const after = src.slice(at, at + 500);
    assert.match(before, /<ol className="num-list /, `${file}: <ol> に num-list`);
    assert.doesNotMatch(after.slice(0, after.indexOf("</ol>")), /\{index \+ 1\}/, `${file}: 文字の番号を足している`);
    assert.match(after, /stripListNumber\(/, `${file}: 頭の番号を外していない`);
  }
  const guide = read("app/guides/[slug]/page.tsx");
  const howto = guide.slice(guide.indexOf("guide.howto.map") - 200, guide.indexOf("guide.howto.map") + 400);
  assert.match(howto, /num-list/);
  assert.doesNotMatch(howto, /\{index \+ 1\}/);
});
