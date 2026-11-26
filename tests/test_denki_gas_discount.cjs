const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 冬の電気・ガス料金支援の計算（lib/denki-gas-discount.ts・/tools/denki-gas-discount。2026-11-26）。Next.js を起動せずに検査する。
// 単価と期間は、経済産業省 資源エネルギー庁「電気・ガス料金支援」特設サイト（https://denkigas-gekihenkanwa.go.jp/。2026-11-26 確認）。
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
const dg = load("lib/denki-gas-discount.ts");
const { CALCULATORS, calculatorForArticle, calculatorForGuide } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

test("値引き単価は特設サイトどおり（12月使用分 1.0円・4.0円、1月・2月使用分 4.5円・18.0円。高圧は注記だけ）", () => {
  const [dec, jan, feb] = dg.DENKI_GAS_MONTHS;
  assert.deepEqual([dec.key, dec.electricity, dec.electricityHigh, dec.gas], ["dec", 1.0, 0.5, 4.0]);
  assert.deepEqual([jan.key, jan.electricity, jan.electricityHigh, jan.gas], ["jan", 4.5, 2.3, 18.0]);
  assert.deepEqual([feb.key, feb.electricity, feb.electricityHigh, feb.gas], ["feb", 4.5, 2.3, 18.0]);
  assert.equal(dec.label, "2026年12月使用分");
  assert.equal(feb.label, "2027年2月使用分");
  assert.equal(dg.unitPrice(18), "18.0円");
  assert.equal(dg.unitPrice(4.5), "4.5円");
});

test("値引き額＝単価×使用量。1月・2月の初期値は12月×1.2の四捨五入", () => {
  assert.equal(dg.winterUsage(260), 312);
  assert.equal(dg.winterUsage(30), 36);
  assert.equal(dg.winterUsage(15), 18);
  assert.equal(dg.winterUsage(0), 0);
  const r = dg.denkiGasDiscount(dg.inputFromDecember(260, 30));
  // 12月: 260×1.0＋30×4.0＝380円。1月・2月: 312×4.5＋36×18.0＝1,404＋648＝2,052円
  assert.deepEqual(r.months.map((m) => [m.electricity, m.gas, m.total]), [[260, 120, 380], [1404, 648, 2052], [1404, 648, 2052]]);
  assert.equal(r.electricity, 3068);
  assert.equal(r.gas, 1416);
  assert.equal(r.total, 4484);
  // 0.5円の端数はそのまま残す（4.5×151＝679.5）
  const odd = dg.denkiGasDiscount({ dec: { electricity: 0, gas: 0 }, jan: { electricity: 151, gas: 0 }, feb: { electricity: 0, gas: 0 } });
  assert.equal(odd.total, 679.5);
  assert.equal(dg.yenDecimal(679.5), "679.5円");
  assert.equal(dg.yenDecimal(4484), "4,484円");
});

test("プロパンガスはガスの値引きを0円にする", () => {
  const r = dg.denkiGasDiscount(dg.inputFromDecember(260, 30, true));
  assert.equal(r.gas, 0);
  assert.equal(r.total, 3068);
  // マイナスや読めない数字は0として扱う
  const bad = dg.denkiGasDiscount({ dec: { electricity: -5, gas: NaN }, jan: { electricity: 0, gas: 0 }, feb: { electricity: 0, gas: 0 } });
  assert.equal(bad.total, 0);
});

test("例の表は denkiGasDiscount() から作り、ページは数字を手で書かない", () => {
  const table = dg.denkiGasExampleTable();
  assert.equal(table.length, dg.DENKI_GAS_EXAMPLES.length);
  for (const [i, row] of table.entries()) {
    const ex = dg.DENKI_GAS_EXAMPLES[i];
    const r = dg.denkiGasDiscount(dg.inputFromDecember(ex.electricity, ex.gas));
    assert.equal(row.total, r.total);
    assert.equal(row.dec + row.jan + row.feb, row.total);
  }
  const byLabel = Object.fromEntries(table.map((row) => [row.label, [row.dec, row.jan, row.feb, row.total]]));
  // 150×1.0＋15×4.0＝210、180×4.5＋18×18＝810＋324＝1,134
  assert.deepEqual(byLabel["一人暮らし（例）"], [210, 1134, 1134, 2478]);
  // 250＋100＝350、300×4.5＋30×18＝1,350＋540＝1,890
  assert.deepEqual(byLabel["2人暮らし（例）"], [350, 1890, 1890, 4130]);
  // 400＋160＝560、480×4.5＋48×18＝2,160＋864＝3,024
  assert.deepEqual(byLabel["4人家族（例）"], [560, 3024, 3024, 6608]);
  const src = read("app/tools/denki-gas-discount/page.tsx");
  assert.match(src, /denkiGasExampleTable\(\)/);
  assert.doesNotMatch(src, /[0-9]{1,3},[0-9]{3}円/);
  for (const rel of ["app/tools/denki-gas-discount/page.tsx", "lib/denki-gas-discount.ts", "components/calc/DenkiGasDiscountCalc.tsx"]) {
    assert.doesNotMatch(read(rel), /｜|ざっくり|の人へ/, rel);
  }
  for (const id of ["what", "meisai", "not-covered", "scam", "example", "sources", "guides"]) assert.match(src, new RegExp(`<ToolSection id="${id}"`));
  assert.match(src, /title: "うちの電気代・ガス代は冬にいくら安くなる？/);
  assert.match(src, /toolAd\("energy"\)/);
  assert.match(src, /\/articles\/winter-electricity-gas-subsidy-2026/);
  assert.match(src, /href: "\/dates"/);
});

test("計算機の登録：CALCULATORS・記事とガイドからの案内・関連の記事・広告", () => {
  const meta = CALCULATORS["denki-gas-discount"];
  assert.equal(meta.href, "/tools/denki-gas-discount");
  assert.equal(meta.checked, "2026-11-26");
  const base = { title: "", tags: [], genreSlug: "public" };
  assert.equal(calculatorForArticle({ ...base, title: "冬の電気代、2027年1・2月使用分は1kWhあたり4.5円引き　申請は不要" }).kind, "denki-gas-discount");
  assert.equal(calculatorForArticle({ ...base, title: "電気・ガス料金支援は12月使用分から自動値引き" }).kind, "denki-gas-discount");
  assert.equal(calculatorForArticle({ ...base, title: "燃料費調整額、12月分は上がる", tags: ["電気代"] }), null);
  assert.equal(calculatorForGuide({ title: "電気・ガス料金支援の受け方" }), "denki-gas-discount");
  const money = load("lib/money-pages.ts");
  assert.ok(money.moneyRowsForTool("/tools/denki-gas-discount").some((row) => row.key === "denki-gas-discount"));
  for (const slug of money.MONEY_PAGES.find((row) => row.key === "denki-gas-discount").articles) {
    assert.ok(fs.existsSync(path.join(root, "content/articles", `${slug}.json`)), slug);
  }
  assert.ok(load("lib/guide-ads.ts").GUIDE_AD_RULES.some((rule) => rule.key === "energy"));
  assert.match(read("components/calc/CalculatorBox.tsx"), /calc\.kind === "denki-gas-discount"\) return <DenkiGasDiscountCalc \/>/);
  assert.match(read("lib/sitemap.ts"), /"\/tools\/denki-gas-discount"[^\]]*\]\.map\(fixed\)/);
  assert.match(read("components/Footer.tsx"), /\/tools\/denki-gas-discount/);
  assert.match(read("app/choose/page.tsx"), /CALCULATORS\["denki-gas-discount"\]/);
  assert.match(read("lib/page-share.ts"), /"denki-gas-discount": \{ heading:/);
});
