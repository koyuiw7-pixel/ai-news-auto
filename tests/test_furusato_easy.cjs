const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// ふるさと納税の上限額「年収から（かんたん）」（lib/furusato-easy.ts。2026-11-11 COMPARE-1）。
// 総務省が2025年10月まで載せていた目安表（tests/fixtures/soumu_furusato_table_20251023.json）と突き合わせる。
const root = path.resolve(__dirname, "..");
function load(rel) {
  const file = path.join(root, rel);
  const out = ts.transpileModule(fs.readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod._compile(out, file);
  return mod.exports;
}
const easy = load("lib/furusato-easy.ts");
const table = JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/soumu_furusato_table_20251023.json"), "utf8"));
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

test("総務省の目安表（年収300万〜900万円・7つの家族構成）と175か所中174か所で一致し、残りも1,000円の丸めの差だけ", () => {
  assert.deepEqual(table.columns, easy.FURUSATO_FAMILIES.map((f) => f.key));
  let same = 0;
  const diffs = [];
  for (const [salary, cells] of Object.entries(table.rows)) {
    if (+salary > 9000000) continue;
    easy.FURUSATO_FAMILIES.forEach((f, i) => {
      const r = easy.furusatoEasy({ salary: +salary, ...f.family });
      const got = r && r.rounded >= 3000 ? r.rounded : null;
      if (got === cells[i]) same++;
      else diffs.push({ salary: +salary, key: f.key, expected: cells[i], got, limit: r.limit });
    });
  }
  assert.equal(same, 174);
  assert.equal(diffs.length, 1);
  assert.deepEqual([diffs[0].salary, diffs[0].key, diffs[0].expected], [8750000, "couple-both", 114000]);
  assert.ok(diffs[0].expected - diffs[0].limit <= 14, "計算では14円の差");
});

test("年収900万円超は総務省の表より少なめ（社会保険料15%は多めの仮定）で、寄附しすぎにならない", () => {
  for (const [salary, cells] of Object.entries(table.rows)) {
    if (+salary <= 9000000) continue;
    easy.FURUSATO_FAMILIES.forEach((f, i) => {
      const r = easy.furusatoEasy({ salary: +salary, ...f.family });
      assert.ok(r.rounded <= cells[i], `${salary} ${f.key}`);
    });
  }
});

test("代表的な例（独身・年収500万円 → 61,000円、夫婦・年収700万円 → 86,000円）", () => {
  assert.equal(easy.furusatoEasy({ salary: 5000000, spouse: false, teens: 0, students: 0 }).rounded, 61000);
  assert.equal(easy.furusatoEasy({ salary: 7000000, spouse: true, teens: 0, students: 0 }).rounded, 86000);
  assert.equal(easy.furusatoManYen(61000), "6.1");
  assert.equal(easy.furusatoManYen(100000), "10");
  assert.equal(easy.furusatoManYen(177000), "17.7");
});

test("くわしい入力: 社会保険料を入れると変わり、iDeCo・ほかの控除は上限を下げる", () => {
  const base = { salary: 6000000, spouse: false, teens: 0, students: 0 };
  const a = easy.furusatoEasy(base);
  assert.equal(a.socialInsurance, 900000);
  assert.ok(easy.furusatoEasy({ ...base, socialInsurance: 800000 }).limit > a.limit);
  assert.ok(easy.furusatoEasy({ ...base, ideco: 276000 }).limit < a.limit);
  assert.ok(easy.furusatoEasy({ ...base, otherDeductions: 100000 }).limit < a.limit);
  assert.equal(easy.furusatoEasy({ ...base, salary: 0 }), null);
});

test("所得税の目安（2026年分）：独身・年収500万円 → 88,500円（基礎控除104万円・社会保険料15%）", () => {
  assert.equal(easy.incomeTaxEstimate({ salary: 5000000, spouse: false, teens: 0, students: 0 }), 88500);
  assert.equal(easy.salaryIncome(5000000), 3560000);
  assert.equal(easy.salaryIncome(2000000), 1260000); // 最低保障74万円
});

test("ページ: 「年収から」が既定、表は計算で出す、前提と出典（総務省の写し）を書く", () => {
  const calc = read("components/calc/FurusatoLimitCalc.tsx");
  assert.match(calc, /useState<Mode>\("easy"\)/);
  assert.match(calc, /万円まで寄附して、負担は2,000円/);
  assert.match(calc, /社会保険料は年収の15%/);
  const page = read("app/tools/furusato-limit/page.tsx");
  assert.match(page, /furusatoEasyTable\(\)/);
  assert.match(page, /web\.archive\.org\/web\/20251023154903/);
  assert.match(page, /175か所のうち174か所/);
  assert.doesNotMatch(page, /61,000円|61000/);
  assert.doesNotMatch(page, /最安|No\.1(?!\d)|日本一/);
});

test("防衛特別所得税の計算機にも「年収から」（独身・年収600万円 → 所得税額144,500円）", () => {
  assert.equal(easy.incomeTaxEstimate({ salary: 6000000, spouse: false, teens: 0, students: 0 }), 144500);
  const src = read("components/calc/DefenseTaxCalc.tsx");
  assert.match(src, /\{ value: "salary", label: "年収から" \}/);
  assert.match(src, /incomeTaxEstimate\(/);
});
