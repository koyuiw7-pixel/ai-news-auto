const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 冬のボーナスの手取りの計算（lib/bonus-tedori.ts・/tools/bonus-tedori。2026-11-26）。Next.js を起動せずに検査する。
// 率は協会けんぽ（令和8年度の都道府県単位保険料率・介護1.62%・支援金0.23%・保険料額表）、厚生労働省（2026年度の雇用保険料率 5/1,000）、
// 国税庁「賞与に対する源泉徴収税額の算出率の表（令和8年分）」（2026-11-26 確認）。
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
const b = load("lib/bonus-tedori.ts");
const { CALCULATORS, calculatorForArticle } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

test("計算の例：賞与50万円・前月30万円・扶養0人・東京都・40歳未満 → 手取り400,420円", () => {
  const r = b.bonusTedori(b.BONUS_EXAMPLE);
  assert.deepEqual(
    [r.standard, r.health, r.kaigo, r.shien, r.pension, r.koyo, r.social, r.taxRate, r.tax, r.takeHome],
    [500000, 24625, 0, 575, 45750, 2500, 73450, 6.126, 26130, 400420],
  );
  // 40歳から64歳まで：介護保険料 500,000×0.81%＝4,050円。健康保険料と合わせると協会けんぽの表の 11.47%÷2 と同じ
  const k = b.bonusTedori({ ...b.BONUS_EXAMPLE, kaigo: true });
  assert.equal(k.kaigo, 4050);
  assert.equal(k.health + k.kaigo, 28675);
  assert.equal(k.tax, 25882);
  assert.equal(k.takeHome, 396618);
});

test("国税庁の設例：賞与554,000円・社会保険料85,593円・前月196,616円・扶養2人 → 率2.042%・税額9,564円", () => {
  assert.equal(b.bonusTaxRate(196616, 2), 2.042);
  assert.equal(Math.floor((468407 * 2042) / 100000), 9564);
  assert.deepEqual(b.bonusTaxBand(196616, 2), { from: 143000, to: 276000 });
});

test("算出率の表（甲欄）は令和8年分の表どおり", () => {
  assert.equal(b.BONUS_TAX_RATES.length, 21);
  assert.equal(b.BONUS_TAX_KOU.length, 8);
  for (const column of b.BONUS_TAX_KOU) {
    assert.equal(column.length, 20);
    for (let i = 1; i < column.length; i++) assert.ok(column[i] > column[i - 1]);
  }
  // 各欄の最初（0.000% の未満）と最後（45.945% の以上）
  assert.deepEqual(b.BONUS_TAX_KOU.map((c) => c[0]), [82, 107, 143, 181, 218, 251, 284, 317]);
  assert.deepEqual(b.BONUS_TAX_KOU.map((c) => c[19]), [3495, 3527, 3559, 3590, 3622, 3654, 3685, 3717]);
  // 境目は「以上」で次の行
  assert.equal(b.bonusTaxRate(81999, 0), 0);
  assert.equal(b.bonusTaxRate(82000, 0), 2.042);
  assert.equal(b.bonusTaxRate(259999, 0), 4.084);
  assert.equal(b.bonusTaxRate(260000, 0), 6.126);
  assert.equal(b.bonusTaxRate(300000, 3), 4.084);
  assert.equal(b.bonusTaxRate(400000, 1), 10.21);
  assert.equal(b.bonusTaxRate(3600000, 7), 41.861);
  assert.equal(b.bonusTaxRate(5000000, 9), 45.945);
});

test("協会けんぽの料率：47都道府県、介護1.62%・支援金0.23%・厚生年金18.3%・雇用保険5/1,000", () => {
  assert.equal(b.KYOKAI_HEALTH_RATES.length, 47);
  assert.equal(b.prefectureRate("東京都"), 9.85);
  assert.equal(b.prefectureRate("北海道"), 10.28);
  assert.equal(b.prefectureRate("新潟県"), 9.21);
  assert.equal(b.prefectureRate("佐賀県"), 10.55);
  assert.equal(b.prefectureRate("沖縄県"), 9.44);
  assert.equal(b.prefectureRate("大阪府"), 10.13);
  assert.equal(b.KYOKAI_KAIGO_RATE, 1.62);
  assert.equal(b.KYOKAI_SHIEN_RATE, 0.23);
  assert.equal(b.KOSEI_NENKIN_RATE, 18.3);
  assert.equal(b.KOYO_RATE_PER_MILLE, 5);
  assert.equal(b.KOSEI_NENKIN_BONUS_CAP, 1500000);
  assert.equal(b.HEALTH_BONUS_YEARLY_CAP, 5730000);
});

test("標準賞与額・上限・端数", () => {
  assert.equal(b.standardBonus(512345), 512000);
  // 厚生年金は150万円まで
  const big = b.bonusTedori({ ...b.BONUS_EXAMPLE, bonus: 2000000, prevNet: 600000 });
  assert.equal(big.pensionStandard, 1500000);
  assert.equal(big.pension, 137250);
  assert.equal(big.health, 98500);
  // 50銭以下は切り捨て、50銭を超えると切り上げ
  assert.equal(b.roundShare(100.5), 100);
  assert.equal(b.roundShare(100.51), 101);
  // 雇用保険料は1,000円未満を切り捨てない額に掛ける（512,345×5/1,000＝2,561.725 → 2,562）
  assert.equal(b.bonusTedori({ ...b.BONUS_EXAMPLE, bonus: 512345 }).koyo, 2562);
});

test("算出率の表を使えないとき（前月の給与が無い・10倍を超える）は所得税を出さない", () => {
  const none = b.bonusTedori({ ...b.BONUS_EXAMPLE, prevNet: 0 });
  assert.equal(none.tax, null);
  assert.equal(none.taxNote, "no-prev");
  assert.equal(none.takeHome, 500000 - none.social);
  const over = b.bonusTedori({ ...b.BONUS_EXAMPLE, prevNet: 40000 });
  assert.equal(over.tax, null);
  assert.equal(over.taxNote, "over-10x");
});

test("健康保険組合は入れた本人負担の率で計算する", () => {
  const r = b.bonusTedori({ ...b.BONUS_EXAMPLE, insurer: "kumiai", kumiaiHealth: 4.5, kumiaiShien: 0.1, kaigo: true, kumiaiKaigo: 0.9 });
  assert.equal(r.health, 22500);
  assert.equal(r.shien, 500);
  assert.equal(r.kaigo, 4500);
});

test("ページ：例の数字は計算で出し、表・出典・使わない文字を確かめる", () => {
  const src = read("app/tools/bonus-tedori/page.tsx");
  assert.match(src, /title: "冬のボーナス、手取りはいくら？ 社会保険料と所得税を引いた額を計算"/);
  assert.match(src, /bonusTedori\(BONUS_EXAMPLE\)/);
  assert.match(src, /bonusExampleTable\(\)/);
  assert.match(src, /<table/);
  // 例の金額は手で書かない（ふるさと納税の「自己負担2,000円」と標準賞与額の「1,000円未満」は制度の決まりなので除く）
  assert.doesNotMatch(src.replace("自己負担2,000円", "").replace(/1,000円未満/g, ""), /[0-9]{1,3},[0-9]{3}円/);
  assert.match(src, /住民税は引かれません/);
  assert.match(src, /サイソク編集部の計算/);
  for (const id of ["what", "example", "faq", "sources", "guides"]) assert.match(src, new RegExp(`<ToolSection id="${id}"`));
  assert.match(src, /toolAd\("furusato"\)/);
  for (const rel of ["app/tools/bonus-tedori/page.tsx", "lib/bonus-tedori.ts", "components/calc/BonusTedoriCalc.tsx"]) {
    assert.doesNotMatch(read(rel), /｜|ざっくり|の人へ/, rel);
  }
  for (const s of Object.values(b.BONUS_SOURCES)) assert.match(s.href, /^https:\/\/www\.(nta\.go\.jp|kyoukaikenpo\.or\.jp|mhlw\.go\.jp)\//);
  assert.match(read("components/calc/BonusTedoriCalc.tsx"), /BONUS_EXAMPLE\.bonus/);
});

test("計算機の登録：CALCULATORS・記事からの案内・関連の記事・サイトマップ", () => {
  const meta = CALCULATORS["bonus-tedori"];
  assert.equal(meta.href, "/tools/bonus-tedori");
  assert.equal(meta.checked, "2026-11-26");
  const base = { title: "", tags: [], genreSlug: "public" };
  assert.equal(calculatorForArticle({ ...base, title: "冬のボーナス50万円の手取りは約40万円" }).kind, "bonus-tedori");
  assert.equal(calculatorForArticle({ ...base, title: "給与明細の見方", tags: ["ボーナス"] }), null);
  const money = load("lib/money-pages.ts");
  const row = money.moneyRowsForTool("/tools/bonus-tedori").find((r) => r.key === "bonus-tedori");
  assert.ok(row);
  for (const slug of row.articles) assert.ok(fs.existsSync(path.join(root, "content/articles", `${slug}.json`)), slug);
  assert.match(read("components/calc/CalculatorBox.tsx"), /calc\.kind === "bonus-tedori"\) return <BonusTedoriCalc \/>/);
  assert.match(read("lib/sitemap.ts"), /"\/tools\/bonus-tedori"[^\]]*\]\.map\(fixed\)/);
  assert.match(read("components/Footer.tsx"), /\/tools\/bonus-tedori/);
  assert.match(read("app/choose/page.tsx"), /CALCULATORS\["bonus-tedori"\]/);
  assert.match(read("lib/page-share.ts"), /"bonus-tedori": \{ heading:/);
});
