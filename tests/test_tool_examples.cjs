const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 計算ページ（/tools/*）の「計算の例」・JSON-LD の dateModified（LLMO-A7、2026-11-10）。Next.js を起動せずに検査する。
const root = path.resolve(__dirname, "..");
const cache = {};
function load(rel) {
  if (cache[rel]) return cache[rel];
  const file = path.join(root, rel);
  const out = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  const original = mod.require.bind(mod);
  mod.require = (name) => (name.startsWith("@/lib/") ? load(`lib/${name.slice(6)}.ts`) : original(name));
  mod._compile(out, file);
  cache[rel] = mod.exports;
  return mod.exports;
}
const calc = load("lib/calc-math.ts");
const { CALCULATORS, toolPageJsonLd, checkedDateJa } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

test("ふるさと納税の「計算の例」の表は4行×4列で、各セルが furusatoLimit() の値", () => {
  assert.deepEqual([...calc.FURUSATO_EXAMPLE_LEVIES], [100000, 200000, 300000, 500000]);
  assert.deepEqual([...calc.FURUSATO_EXAMPLE_RATES], [5, 10, 20, 23]);
  const table = calc.furusatoExampleTable();
  assert.equal(table.length, 4);
  for (const row of table) {
    assert.equal(row.cells.length, 4);
    for (const cell of row.cells) {
      assert.equal(cell.limit, calc.furusatoLimit(row.levy, cell.rate).limit);
      assert.ok(cell.limit > 2000);
    }
  }
});

test("ふるさと納税の例：所得割額300,000円・税率10% → 77,197円", () => {
  assert.deepEqual(calc.FURUSATO_EXAMPLE, { levy: 300000, rate: 10 });
  const r = calc.furusatoLimit(300000, 10);
  assert.equal(r.limit, 77197);
  assert.equal(r.cap, 60000);
  const cell = calc.furusatoExampleTable().find((row) => row.levy === 300000).cells.find((c) => c.rate === 10);
  assert.equal(cell.limit, 77197);
});

test("ふるさと納税のページは表と例を計算で出し、数字を手で書かない", () => {
  const src = read("app/tools/furusato-limit/page.tsx");
  assert.match(src, /furusatoExampleTable\(\)/);
  assert.match(src, /furusatoLimit\(FURUSATO_EXAMPLE\.levy, FURUSATO_EXAMPLE\.rate\)/);
  assert.match(src, /<table/);
  assert.doesNotMatch(src, /77,197|77197/);
  // 計算の例は計算機より下（ToolPage の children）。広告（afterCalc）の位置は変えない
  assert.match(src, /afterCalc=\{ad \?/);
});

test("防衛特別所得税の例の文は、計算機の最初の値と同じ定数を使う", () => {
  assert.equal(calc.DEFENSE_TAX_DEFAULT_BASE, 150000);
  assert.equal(calc.defenseTaxExampleSentence(calc.DEFENSE_TAX_DEFAULT_BASE), "例：1年の所得税額（基準所得税額）が150,000円の場合");
  const page = read("app/tools/defense-tax/page.tsx");
  assert.match(page, /const EXAMPLE_BASE = DEFENSE_TAX_DEFAULT_BASE;/);
  assert.match(page, /defenseTaxExampleSentence\(EXAMPLE_BASE\)/);
  const calcSrc = read("components/calc/DefenseTaxCalc.tsx");
  assert.match(calcSrc, /defaultBase = DEFENSE_TAX_DEFAULT_BASE/);
  assert.doesNotMatch(calcSrc, /150000/);
  // 例の税額（150,000円 → 2026年分も2027〜2037年分も合計3,150円、2048年分から1,500円）
  assert.equal(calc.surtax(150000, 2026).total, 3150);
  assert.equal(calc.surtax(150000, 2030).total, 3150);
  assert.equal(calc.surtax(150000, 2050).total, 1500);
});

test("JSON-LD の dateModified は出典を確かめた日（CHECKED）で、ビルドの日ではない", () => {
  const site = { url: "https://ai-tech-express.jp", siteName: "サイソク" };
  for (const kind of Object.keys(CALCULATORS)) {
    const checked = CALCULATORS[kind].checked;
    assert.match(checked, /^\d{4}-\d{2}-\d{2}$/);
    const app = toolPageJsonLd(kind, site).find((item) => item["@type"] === "WebApplication");
    assert.equal(app.dateModified, checked);
    assert.equal(app.url, `${site.url}${CALCULATORS[kind].href}`);
  }
  assert.equal(CALCULATORS["furusato-limit"].checked, "2026-11-10");
  assert.equal(CALCULATORS["defense-tax"].checked, "2026-11-03");
  assert.equal(checkedDateJa("2026-11-03"), "2026年11月3日");
  const tool = read("components/calc/ToolPage.tsx");
  assert.match(tool, /toolPageJsonLd\(kind, siteConfig\)/);
  assert.doesNotMatch(tool, /new Date\(/);
  assert.match(tool, /<h2 id=\{id\}/);
});

test("見出しに id、定義とよくある質問があり、使わない文字は無い", () => {
  for (const rel of ["app/tools/furusato-limit/page.tsx", "app/tools/defense-tax/page.tsx"]) {
    const src = read(rel);
    assert.doesNotMatch(src, /<ToolSection title=/, `${rel}: id の無い章がある`);
    assert.match(src, /<ToolSection id="what"/);
    assert.match(src, /<ToolSection id="example" title="計算の例"/);
    assert.match(src, /<ToolSection id="faq" title="よくある質問"/);
    assert.equal((src.match(/<h3 /g) || []).length, 3);
    assert.doesNotMatch(src, /｜|ざっくり/);
    // 日付は CALCULATORS の checked から出す
    assert.doesNotMatch(src, /2026-11-\d\d確認/);
  }
});
