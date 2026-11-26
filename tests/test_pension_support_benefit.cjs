const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 年金生活者支援給付金の計算（lib/pension-support-benefit.ts・/tools/pension-support-benefit。2026-11-26）。Next.js を起動せずに検査する。
// 金額・基準額・式は、日本年金機構「老齢（補足的老齢）年金生活者支援給付金」「障害年金生活者支援給付金」「遺族年金生活者支援給付金」
// （いずれも 2026年10月1日更新）と「令和8年4月分からの年金生活者支援給付金額について」（2026-11-26 確認）。
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
const ps = load("lib/pension-support-benefit.ts");
const { CALCULATORS, calculatorForArticle, calculatorForGuide } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const NONE = { general: 0, elderly: 0, specified: 0 };
const old = (patch = {}) => ({
  kind: "old", age65: true, household: "yes", birth: "after", pensionIncome: 700000, otherIncome: 0,
  paidMonths: 480, exemptFullMonths: 0, exemptQuarterMonths: 0, ...patch,
});

test("令和8年度の額と基準額は日本年金機構のページどおり", () => {
  const P = ps.PENSION_SUPPORT;
  assert.equal(P.base, 5620);
  assert.equal(P.disability1, 7025);
  assert.equal(P.disability2, 5620);
  assert.equal(P.survivor, 5620);
  assert.equal(P.months, 480);
  assert.deepEqual({ ...P.exempt.after }, { full: 11768, quarter: 5884 });
  assert.deepEqual({ ...P.exempt.before }, { full: 11734, quarter: 5867 });
  assert.deepEqual({ ...P.threshold.after }, { base: 826500, upper: 926500 });
  assert.deepEqual({ ...P.threshold.before }, { base: 824100, upper: 924100 });
  assert.equal(P.incomeLimit, 4918000);
  assert.deepEqual({ ...P.dependent }, { general: 380000, elderly: 480000, specified: 630000 });
  assert.equal(ps.PENSION_SUPPORT_CONTACTS.kyufukin.number, "0570-05-4092");
  assert.equal(ps.PENSION_SUPPORT_CONTACTS.nenkin.number, "0570-05-1165");
});

test("老齢：公式ページの計算例（240か月納付＋60か月全額免除＝4,281円）と年金Q&Aの例（420か月＝4,918円）", () => {
  assert.deepEqual(ps.oldAgeAmount("after", 240, 60, 0), { paid: 2810, exempt: 1471, total: 4281 });
  // 5,620×420÷480＝4,917.5 → 50銭以上は1円に切り上げ
  assert.equal(ps.oldAgeAmount("after", 420, 0, 0).total, 4918);
  assert.equal(ps.oldAgeAmount("after", 480, 0, 0).total, 5620);
  // 4分の1免除は 5,884円（昭和31年4月1日以前生まれの全額免除は 11,734円）
  assert.equal(ps.oldAgeAmount("after", 0, 0, 480).total, 5884);
  assert.equal(ps.oldAgeAmount("before", 0, 480, 0).total, 11734);
  assert.equal(ps.roundYen(1, 2), 1);
  assert.equal(ps.roundYen(49, 100), 0);
});

test("老齢の判定：基準額の境目・補足的・対象外・確かめる必要あり", () => {
  assert.equal(ps.pensionSupport(old({ pensionIncome: 826500 })).verdict, "eligible");
  assert.equal(ps.pensionSupport(old({ pensionIncome: 826501 })).verdict, "supplement");
  // 調整支給率＝（926,500−876,500）÷100,000＝0.5 → 5,620×0.5＝2,810円。年金収入とその他の所得は足して判定
  const half = ps.pensionSupport(old({ pensionIncome: 800000, otherIncome: 76500 }));
  assert.equal(half.verdict, "supplement");
  assert.equal(half.monthly, 2810);
  assert.equal(half.perPayment, 5620);
  assert.equal(half.annual, 33720);
  // 補足的は免除の期間を入れない（5,620×240÷480×0.5＝1,405円）
  assert.equal(ps.supplementAmount("after", 240, 876500), 1405);
  assert.equal(ps.pensionSupport(old({ paidMonths: 240, exemptFullMonths: 60, pensionIncome: 876500 })).monthly, 1405);
  // 上限ちょうどは補足的の対象（調整支給率0で0円）、1円でも超えれば対象外
  assert.equal(ps.pensionSupport(old({ pensionIncome: 926500 })).verdict, "supplement");
  assert.equal(ps.pensionSupport(old({ pensionIncome: 926501 })).verdict, "ineligible");
  // 昭和31年4月1日以前生まれは 824,100円・924,100円
  assert.equal(ps.pensionSupport(old({ birth: "before", pensionIncome: 825000 })).verdict, "supplement");
  assert.equal(ps.pensionSupport(old({ birth: "before", pensionIncome: 924101 })).verdict, "ineligible");
  assert.equal(ps.pensionSupport(old({ age65: false })).verdict, "ineligible");
  assert.equal(ps.pensionSupport(old({ household: "no" })).verdict, "ineligible");
  const unknown = ps.pensionSupport(old({ household: "unknown" }));
  assert.equal(unknown.verdict, "check");
  assert.equal(unknown.monthly, 5620);
  const veryOld = ps.pensionSupport(old({ birth: "veryOld" }));
  assert.equal(veryOld.verdict, "check");
  assert.equal(veryOld.monthly, null);
  assert.equal(ps.pensionSupport(old({ paidMonths: 480, exemptFullMonths: 1 })).verdict, "check");
});

test("障害・遺族：月額は定額、所得の基準は 4,918,000円＋扶養親族", () => {
  const dis1 = ps.pensionSupport({ kind: "disability", grade: 1, income: 2000000, dependents: NONE });
  assert.deepEqual([dis1.verdict, dis1.monthly, dis1.perPayment, dis1.annual], ["eligible", 7025, 14050, 84300]);
  assert.equal(ps.pensionSupport({ kind: "disability", grade: 2, income: 4918000, dependents: NONE }).verdict, "eligible");
  assert.equal(ps.pensionSupport({ kind: "disability", grade: 2, income: 4918001, dependents: NONE }).verdict, "ineligible");
  assert.equal(ps.incomeLimitFor({ general: 1, elderly: 1, specified: 1 }), 4918000 + 380000 + 480000 + 630000);
  // 3人の子なら 5,620÷3＝1,873.33… → 1,873円（公式ページの例）
  assert.equal(ps.pensionSupport({ kind: "survivor", sharing: 3, income: 0, dependents: NONE }).monthly, 1873);
  assert.equal(ps.pensionSupport({ kind: "survivor", sharing: 1, income: 0, dependents: NONE }).monthly, 5620);
});

test("よくある例の表は pensionSupport() から作り、ページは数字を手で書かない", () => {
  const table = ps.pensionSupportExampleTable();
  assert.equal(table.length, ps.PENSION_SUPPORT_EXAMPLES.length);
  for (const [i, row] of table.entries()) {
    const r = ps.pensionSupport(ps.PENSION_SUPPORT_EXAMPLES[i].input);
    assert.equal(row.monthly, r.monthly ?? 0);
    assert.equal(row.perPayment, row.monthly * 2);
    assert.equal(row.annual, row.monthly * 12);
  }
  const byLabel = Object.fromEntries(table.map((row) => [row.label, [row.verdict, row.monthly]]));
  assert.deepEqual(byLabel["老齢：40年すべて納めた・年金収入70万円"], ["対象の目安", 5620]);
  assert.deepEqual(byLabel["老齢：20年納めた・5年全額免除・年金収入60万円"], ["対象の目安", 4281]);
  assert.deepEqual(byLabel["老齢：40年すべて納めた・年金収入87万6,500円"], ["補足的給付の目安", 2810]);
  assert.deepEqual(byLabel["老齢：40年すべて納めた・年金収入95万円"], ["対象外の目安", 0]);
  const src = read("app/tools/pension-support-benefit/page.tsx");
  assert.match(src, /pensionSupportExampleTable\(\)/);
  assert.doesNotMatch(src, /[0-9]{1,3},[0-9]{3}円/);
  for (const rel of ["app/tools/pension-support-benefit/page.tsx", "lib/pension-support-benefit.ts", "components/calc/PensionSupportCalc.tsx"]) {
    assert.doesNotMatch(read(rel), /｜|ざっくり/, rel);
  }
  for (const id of ["what", "old-age", "disability-survivor", "payment", "example", "faq"]) assert.match(src, new RegExp(`<ToolSection id="${id}"`));
  assert.match(src, /<ToolSection id="faq" title="よくある疑問"/);
  assert.match(src, /title: "年金生活者支援給付金はもらえる？ いくら？/);
});

test("計算機の登録：CALCULATORS・記事とガイドからの案内・関連の記事", () => {
  const meta = CALCULATORS["pension-support-benefit"];
  assert.equal(meta.href, "/tools/pension-support-benefit");
  assert.equal(meta.checked, "2026-11-26");
  const base = { title: "", tags: [], genreSlug: "public" };
  assert.equal(calculatorForArticle({ ...base, title: "年金生活者支援給付金、所得の上限は826,500円か824,100円" }).kind, "pension-support-benefit");
  assert.equal(calculatorForArticle({ ...base, title: "年金の支払日", tags: ["年金生活者支援給付金"] }), null);
  assert.equal(calculatorForGuide({ tool: "nenkin", title: "年金生活者支援給付金の請求のしかた" }), "pension-support-benefit");
  const money = load("lib/money-pages.ts");
  assert.ok(money.moneyRowsForTool("/tools/pension-support-benefit").some((row) => row.key === "pension-support"));
  // 記事の「自分は対象か確かめる」の行き先は変えない
  assert.equal(money.moneyLinkFor({ title: "年金生活者支援給付金のはがき" }).href, "/articles/pension-support-benefit-old-age-check");
  for (const slug of money.MONEY_PAGES.find((row) => row.key === "pension-support").articles) {
    assert.ok(fs.existsSync(path.join(root, "content/articles", `${slug}.json`)), slug);
  }
  assert.match(read("components/calc/CalculatorBox.tsx"), /calc\.kind === "pension-support-benefit"\) return <PensionSupportCalc \/>/);
  assert.match(read("lib/sitemap.ts"), /"\/tools\/pension-support-benefit"[^\]]*\]\.map\(fixed\)/);
  assert.match(read("components/Footer.tsx"), /\/tools\/pension-support-benefit/);
  assert.match(read("app/choose/page.tsx"), /CALCULATORS\["pension-support-benefit"\]/);
  assert.match(read("lib/page-share.ts"), /"pension-support-benefit": \{ heading:/);
});

test("受け取るまでの流れ：はがきを出す・令和9年1月4日・受給中は原則手続き不要・偶数月に年金と同じ口座（日本年金機構 2026-11-27 確認）", () => {
  const g = ps.PENSION_SUPPORT_RECEIVE;
  assert.deepEqual(g.steps.map((s) => s.label), ["誰が", "どこへ", "いつまでに", "いつ入る"]);
  const all = g.steps.map((s) => s.text).join("");
  for (const fact of ["請求書（はがき型）", "緑の封筒", "毎年の手続きは原則いりません", "切手", "電子申請", "年金の請求書と一緒に", "令和9年（2027年）1月4日（月曜）", "令和8年10月分から", "偶数月の中旬", "年金と同じ口座"]) {
    assert.ok(all.includes(fact), fact);
  }
  assert.doesNotMatch(all + g.title, /｜|ざっくり|人へ|→/);
  for (const s of g.sources) assert.match(s.href, /^https:\/\/www\.nenkin\.go\.jp\//);
  assert.ok(g.sources.some((s) => s.href.endsWith("/hagaki/kigen.html")));
  assert.equal(g.checked, "2026-11-27");
  const calc = read("components/calc/PensionSupportCalc.tsx");
  assert.match(calc, /data-pension-support-result[\s\S]*次にすること[\s\S]*<ReceiveSteps guide=\{PENSION_SUPPORT_RECEIVE\} \/>/);
});
