const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 高額療養費の上限額の計算（lib/kogaku-ryoyohi.ts・/tools/kogaku-ryoyohi。2026-11-26）。Next.js を起動せずに検査する。
// 額は厚生労働省「高額療養費制度の見直しについて（令和８年８月診療分から）」（https://www.mhlw.go.jp/content/001726232.pdf）と協会けんぽの案内（2026-11-26 確認）。
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
const kg = load("lib/kogaku-ryoyohi.ts");
const { CALCULATORS, calculatorForArticle, calculatorForGuide } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

test("69歳までの上限額は厚生労働省の表（令和8年8月〜令和9年7月）どおり", () => {
  const rows = kg.bandsFor("under70").map((b) => [b.letter, b.base, b.threshold, b.many, b.yearly]);
  assert.deepEqual(rows, [
    ["ア", 270300, 901000, 140100, 1680000],
    ["イ", 179100, 597000, 93000, 1110000],
    ["ウ", 85800, 286000, 44400, 530000],
    ["エ", 61500, undefined, 44400, 530000],
    ["オ", 36900, undefined, 24600, 290000],
  ]);
  assert.equal(kg.KOGAKU_PERIOD.from, "2026年8月診療分");
  assert.equal(kg.KOGAKU_PERIOD.to, "2027年7月診療分");
});

test("70歳以上は現役並みが同じ式、一般・低所得は定額と外来の上限", () => {
  const rows = kg.bandsFor("75plus").map((b) => [b.key, b.base, b.many, b.yearly, b.outpatient, b.outpatientYearly]);
  assert.deepEqual(rows, [
    ["a", 270300, 140100, 1680000, undefined, undefined],
    ["i", 179100, 93000, 1110000, undefined, undefined],
    ["u", 85800, 44400, 530000, undefined, undefined],
    ["e", 61500, 44400, 530000, 22000, 216000],
    ["o", 25700, 24600, 290000, 11000, 96000],
    ["low1", 15700, undefined, 180000, 8000, undefined],
  ]);
  assert.deepEqual(kg.bandsFor("70to74").map((b) => b.key), kg.bandsFor("75plus").map((b) => b.key));
});

test("上限＝基本額＋(総医療費−基準)×1%。総医療費が無ければ100万円。窓口の負担が少なければ払い戻しなし", () => {
  // 厚労省ページの例: 年収約370万〜約510万円、医療費100万円 → 約9.3万円（85,800＋714,000×1%＝92,940）
  const r = kg.kogaku({ age: "under70", band: "u" });
  assert.equal(r.entered, false);
  assert.equal(r.totalMedical, 1000000);
  assert.equal(r.cap, 92940);
  assert.equal(r.windowShare, 300000);
  assert.equal(r.pay, 92940);
  assert.equal(r.over, 207060);
  assert.equal(kg.kogaku({ age: "under70", band: "a", totalMedical: 1000000 }).pay, 271290);
  assert.equal(kg.kogaku({ age: "under70", band: "i", totalMedical: 1000000 }).pay, 183130);
  // 総医療費50万円の区分ア: 3割の15万円が上限より少ない
  const low = kg.kogaku({ age: "under70", band: "a", totalMedical: 500000 });
  assert.equal(low.pay, 150000);
  assert.equal(low.over, 0);
  // 定額の区分
  assert.equal(kg.kogaku({ age: "under70", band: "e", totalMedical: 3000000 }).cap, 61500);
  assert.equal(kg.kogaku({ age: "under70", band: "o" }).cap, 36900);
  // 1%の端数は四捨五入（表示用）
  assert.equal(kg.monthlyCap(kg.bandOf("under70", "u"), 286050), 85801);
});

test("多数回該当・外来だけ・負担割合", () => {
  assert.equal(kg.kogaku({ age: "under70", band: "u", many: true }).cap, 44400);
  assert.equal(kg.kogaku({ age: "under70", band: "a", many: true }).cap, 140100);
  assert.equal(kg.kogaku({ age: "75plus", band: "low1", many: true }).cap, 15700);
  const out = kg.kogaku({ age: "75plus", band: "e", outpatientOnly: true, totalMedical: 300000 });
  assert.equal(out.cap, 22000);
  assert.equal(out.share, 0.1);
  assert.equal(out.windowShare, 30000);
  assert.equal(out.pay, 22000);
  assert.equal(out.outpatientYearly, 216000);
  assert.equal(kg.kogaku({ age: "70to74", band: "e" }).share, 0.2);
  assert.equal(kg.kogaku({ age: "75plus", band: "e", share: 0.2 }).share, 0.2);
  assert.equal(kg.kogaku({ age: "75plus", band: "u" }).share, 0.3);
  // 69歳までに外来だけは無い（70歳以上だけの仕組み）
  assert.equal(kg.kogaku({ age: "under70", band: "e", outpatientOnly: true }).cap, 61500);
  // 70歳以上に低所得Ⅰを選んで69歳に戻すと、いちばん下（オ）にする
  assert.equal(kg.bandOf("under70", "low1").letter, "オ");
});

test("例の表は kogaku() から作り、ページは数字を手で書かない", () => {
  const table = kg.kogakuExampleTable();
  assert.deepEqual(table.map((r) => [r.band.letter, ...r.pays]), [
    ["ア", 150000, 271290, 281290],
    ["イ", 150000, 183130, 193130],
    ["ウ", 87940, 92940, 102940],
    ["エ", 61500, 61500, 61500],
    ["オ", 36900, 36900, 36900],
  ]);
  const src = read("app/tools/kogaku-ryoyohi/page.tsx");
  assert.match(src, /kogakuExampleTable\(\)/);
  assert.doesNotMatch(src, /[0-9]{1,3},[0-9]{3}円/);
  for (const rel of ["app/tools/kogaku-ryoyohi/page.tsx", "lib/kogaku-ryoyohi.ts", "components/calc/KogakuRyoyohiCalc.tsx"]) {
    assert.doesNotMatch(read(rel), /｜|ざっくり|の人へ/, rel);
  }
  for (const id of ["what", "limits", "senior", "window", "example", "faq", "sources", "guides"]) assert.match(src, new RegExp(`<ToolSection id="${id}"`));
  assert.match(src, /title: "医療費が高額になったら月いくらまで？ 高額療養費の自己負担の上限を年収で計算"/);
  assert.match(src, /サイソク編集部の計算/);
  assert.match(src, /toolAd\("tax"\)/);
  assert.match(read("components/calc/KogakuRyoyohiCalc.tsx"), /マイナ保険証か限度額適用認定証を使えば、窓口の支払いは最初から上限まで/);
  for (const href of Object.values(kg.KOGAKU_SOURCES).map((s) => s.href)) assert.match(href, /^https:\/\/www\.(mhlw\.go\.jp|kyoukaikenpo\.or\.jp)\//);
});

test("計算機の登録：CALCULATORS・記事とガイドからの案内・関連の記事・広告", () => {
  const meta = CALCULATORS["kogaku-ryoyohi"];
  assert.equal(meta.href, "/tools/kogaku-ryoyohi");
  assert.equal(meta.checked, "2026-11-26");
  const base = { title: "", tags: [], genreSlug: "public" };
  assert.equal(calculatorForArticle({ ...base, title: "高額療養費の上限は4回目から44,400円" }).kind, "kogaku-ryoyohi");
  assert.equal(calculatorForArticle({ ...base, title: "医療費控除の対象", tags: ["高額療養費"] }), null);
  assert.equal(calculatorForGuide({ title: "高額療養費の上限額と申請方法" }), "kogaku-ryoyohi");
  const money = load("lib/money-pages.ts");
  const row = money.moneyRowsForTool("/tools/kogaku-ryoyohi").find((r) => r.key === "kogaku-ryoyohi");
  assert.ok(row);
  assert.equal(row.href, "/guides/kogaku-ryoyohi");
  for (const slug of row.articles) assert.ok(fs.existsSync(path.join(root, "content/articles", `${slug}.json`)), slug);
  for (const slug of row.guides) assert.ok(fs.existsSync(path.join(root, "content/howto", `${slug}.json`)), slug);
  assert.match(read("components/calc/CalculatorBox.tsx"), /calc\.kind === "kogaku-ryoyohi"\) return <KogakuRyoyohiCalc \/>/);
  assert.match(read("lib/sitemap.ts"), /"\/tools\/kogaku-ryoyohi"[^\]]*\]\.map\(fixed\)/);
  assert.match(read("components/Footer.tsx"), /\/tools\/kogaku-ryoyohi/);
  assert.match(read("app/choose/page.tsx"), /CALCULATORS\["kogaku-ryoyohi"\]/);
  assert.match(read("lib/page-share.ts"), /"kogaku-ryoyohi": \{ heading:/);
});
