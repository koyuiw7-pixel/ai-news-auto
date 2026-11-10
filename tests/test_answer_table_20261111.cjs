// 2026-11-11 オーナー「弱点になるなら全部改善して」・読者目線レビュー 3位: 答えの表（早見表など）を要点のすぐ下へ。
// 12月の児童手当の早見表はスマホで約4.8画面目だった。最初の2章の表だけ・スマホで読める大きさだけ。表の場所には1行の案内を残す。
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const Module = require("node:module");
const root = path.resolve(__dirname, "..");
const file = path.join(root, "lib/answer-table.ts");
const m = new Module(file, module);
m.filename = file;
m._compile(ts.transpileModule(fs.readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, file);
const { extractAnswerTable, ANSWER_TABLE_ID } = m.exports;

const table = (cols, rows) =>
  `<div class="nr-scroll rv"><table><thead><tr>${"<th>h</th>".repeat(cols)}</tr></thead><tbody>${`<tr>${"<td>1</td>".repeat(cols)}</tr>`.repeat(rows)}</tbody></table></div>`;

test("最初の2章にある表を取り出し、見出しは表のある章の h2。本文には案内の1行を残す", () => {
  const html = `<p>答え</p><h2 id="a">12月の振込額</h2><p>x</p><h2 id="b">早見表（12月の振込額）</h2><p>目安です</p>${table(3, 5)}<p>注</p><h2 id="c">支給日</h2>`;
  const got = extractAnswerTable(html);
  assert.equal(got.caption, "早見表（12月の振込額）");
  assert.match(got.html, /^<div class="nr-scroll rv"><table>/);
  assert.match(got.html, /<\/table><\/div>$/);
  assert.doesNotMatch(got.rest, /<table/);
  assert.match(got.rest, new RegExp(`<p>目安です</p><p class="answer-table-moved"><a href="#${ANSWER_TABLE_ID}">`));
  assert.match(got.rest, /<p>注<\/p><h2 id="c">/);
});

test("3つ目の章より後の表・大きすぎる表・表の無い本文は動かさない", () => {
  assert.equal(extractAnswerTable(`<h2>a</h2><h2>b</h2><h2>c</h2>${table(3, 3)}`), null);
  assert.equal(extractAnswerTable(`<h2>a</h2>${table(6, 3)}`), null);
  assert.equal(extractAnswerTable(`<h2>a</h2>${table(3, 20)}`), null);
  assert.equal(extractAnswerTable("<h2>a</h2><p>表なし</p>"), null);
});

test("ノワール・今までの見た目の両方で、要点のすぐ下に出す。比較記事の表は動かさない", () => {
  const noir = fs.readFileSync(path.join(root, "components/noir/noirArticlePage.tsx"), "utf8");
  assert.match(noir, /const answer = compareInline \? null : extractAnswerTable\(noirHtml\);/);
  assert.match(noir, /splitBeforeHeading\(answer \? answer\.rest : noirHtml, 3\)/);
  const page = fs.readFileSync(path.join(root, "app/articles/[slug]/page.tsx"), "utf8");
  assert.match(page, /const answer = compareInline \? null : extractAnswerTable\(bodyHtml\);/);
  assert.ok(page.indexOf('id="points-heading"') < page.indexOf("{answer && ("));
  assert.ok(page.indexOf("{answer && (") < page.indexOf("<MoneyCheckLink target={moneyLink}"));
});
