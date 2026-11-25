const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 児童手当の支給額の計算（lib/child-allowance.ts・/tools/child-allowance。2026-11-25）。Next.js を起動せずに検査する。
// 金額・数え方・支給月は、こども家庭庁「もっと子育て応援！児童手当」「児童手当制度のご案内」「「第3子以降」のカウント方法について」と
// 児童手当法 第6条・第8条・第9条（2026-11-25 確認）。
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
const ca = load("lib/child-allowance.ts");
const { CALCULATORS, calculatorForArticle, calculatorForGuide } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const cat = (...categories) => categories.map((category) => ({ kind: "category", category }));
const born = (year, month, supported) => ({ kind: "birth", year, month, supported });
const NOV = { year: 2026, month: 11 };

test("月額はこども家庭庁の表どおり（3歳未満15,000円・3歳〜高校生年代10,000円・第3子以降30,000円）", () => {
  assert.deepEqual({ ...ca.CHILD_ALLOWANCE_AMOUNTS }, { under3: 15000, from3: 10000, third: 30000 });
  assert.deepEqual([...ca.CHILD_ALLOWANCE_PAY_MONTHS], [2, 4, 6, 8, 10, 12]);
  assert.equal(ca.monthTotal(cat("under3"), NOV), 15000);
  assert.equal(ca.monthTotal(cat("from3"), NOV), 10000);
  assert.equal(ca.monthTotal(cat("from3", "from3"), NOV), 20000);
  // 第3子以降は年齢に関係なく30,000円
  assert.deepEqual(ca.allowanceForMonth(cat("from3", "from3", "under3"), NOV).map((c) => [c.rank, c.amount]), [[1, 10000], [2, 10000], [3, 30000]]);
  assert.deepEqual(ca.allowanceForMonth(cat("from3", "from3", "from3", "under3"), NOV).map((c) => c.amount), [10000, 10000, 30000, 30000]);
});

test("22歳の年度末までの上の子は、生活費を負担していれば数に入る（手当は無い）。負担がなければ数に入らない", () => {
  const supported = ca.allowanceForMonth(cat("olderSupported", "from3", "from3"), NOV);
  assert.deepEqual(supported.map((c) => [c.status, c.rank, c.amount]), [["olderCounted", 1, 0], ["from3", 2, 10000], ["from3", 3, 30000]]);
  const not = ca.allowanceForMonth(cat("olderNotSupported", "from3", "from3"), NOV);
  assert.deepEqual(not.map((c) => [c.rank, c.amount]), [[null, 0], [1, 10000], [2, 10000]]);
  // 上の子が2人数に入れば、手当の対象の子はみな第3子以降
  assert.equal(ca.monthTotal(cat("olderSupported", "olderSupported", "under3"), NOV), 30000);
});

test("生まれた年月から：年度・3歳の誕生月・18歳と22歳の年度末", () => {
  assert.equal(ca.schoolYearOf(2008, 5), 2008);
  assert.equal(ca.schoolYearOf(2009, 3), 2008);
  // 生まれた月の分は出ない（申請した月の翌月分から）
  assert.equal(ca.statusByBirth({ year: 2026, month: 11 }, NOV), "notBorn");
  assert.equal(ca.statusByBirth({ year: 2026, month: 10 }, NOV), "under3");
  // 3歳の誕生月までは3歳未満、翌月から3歳以上（2023年11月生まれ → 2026年11月は3歳未満、12月から3歳以上）
  assert.equal(ca.statusByBirth({ year: 2023, month: 11 }, NOV), "under3");
  assert.equal(ca.statusByBirth({ year: 2023, month: 11 }, { year: 2026, month: 12 }), "from3");
  // 2008年5月生まれ（高校3年生の年代）: 2027年3月分まで手当、4月から兄姉等、2031年3月まで数に入る
  const c = { year: 2008, month: 5, supported: true };
  assert.equal(ca.statusByBirth(c, { year: 2027, month: 3 }), "from3");
  assert.equal(ca.statusByBirth(c, { year: 2027, month: 4 }), "olderCounted");
  assert.equal(ca.statusByBirth({ ...c, supported: false }, { year: 2027, month: 4 }), "olderNotCounted");
  assert.equal(ca.statusByBirth(c, { year: 2031, month: 3 }), "olderCounted");
  assert.equal(ca.statusByBirth(c, { year: 2031, month: 4 }), "over22");
  // 1〜3月生まれは前の年度（2009年2月生まれも2027年3月が18歳の年度末）
  assert.equal(ca.statusByBirth({ year: 2009, month: 2 }, { year: 2027, month: 3 }), "from3");
  assert.equal(ca.statusByBirth({ year: 2009, month: 2 }, { year: 2027, month: 4 }), "olderNotCounted");
});

test("12月の支給は10月・11月分の合計。偶数月以外は支給月にならない", () => {
  const kids = [born(2017, 6), born(2023, 11)];
  const r = ca.childAllowance(kids);
  assert.deepEqual(r.next.pay, { year: 2026, month: 12 });
  assert.deepEqual(r.next.months, [{ year: 2026, month: 10 }, { year: 2026, month: 11 }]);
  // 10月・11月とも 10,000円＋15,000円（2023年11月生まれは11月が3歳の誕生月なので、まだ3歳未満の額）
  assert.equal(r.next.amount, 50000);
  assert.equal(r.monthly, 25000);
  assert.throws(() => ca.paymentFor(kids, { year: 2026, month: 11 }));
});

test("1年分は12月から6回（2026年10月〜2027年9月分）で、年齢が上がった月から額が変わる", () => {
  const kids = [born(2017, 6), born(2023, 11)];
  const r = ca.childAllowance(kids);
  assert.deepEqual(r.year.payments.map((p) => `${p.pay.year}-${p.pay.month}`), ["2026-12", "2027-2", "2027-4", "2027-6", "2027-8", "2027-10"]);
  // 10・11月は 25,000円、12月から 20,000円 → 25,000×2＋20,000×10
  assert.equal(r.year.total, 25000 * 2 + 20000 * 10);
  // 上の子が22歳の年度末を過ぎると数から外れ、第3子が第2子になる（2004年5月生まれ → 2027年3月が22歳の年度末）
  const family = [born(2004, 5, true), born(2010, 8), born(2015, 4)];
  const before = ca.allowanceForMonth(family, { year: 2027, month: 3 });
  const after = ca.allowanceForMonth(family, { year: 2027, month: 4 });
  assert.deepEqual(before.map((c) => c.amount), [0, 10000, 30000]);
  assert.deepEqual(after.map((c) => c.amount), [0, 10000, 10000]);
  assert.equal(after[0].status, "over22");
  // 入れた順に関係なく、生まれた年月が早い子から数える
  const shuffled = [family[2], family[0], family[1]];
  assert.deepEqual(ca.allowanceForMonth(shuffled, { year: 2027, month: 3 }).map((c) => c.amount), [30000, 0, 10000]);
});

test("よくある家族の例の表は childAllowance() から作り、ページは数字を手で書かない", () => {
  const table = ca.childAllowanceExampleTable();
  assert.equal(table.length, ca.CHILD_ALLOWANCE_EXAMPLES.length);
  for (const [i, row] of table.entries()) {
    const r = ca.childAllowance(cat(...ca.CHILD_ALLOWANCE_EXAMPLES[i].children));
    assert.deepEqual(row, { label: ca.CHILD_ALLOWANCE_EXAMPLES[i].label, monthly: r.monthly, payment: r.next.amount, year: r.year.total });
    assert.equal(row.payment, row.monthly * 2);
    assert.equal(row.year, row.monthly * 12);
  }
  const byLabel = Object.fromEntries(table.map((row) => [row.label, row.monthly]));
  assert.equal(byLabel["小学生2人と3歳未満"], 50000);
  assert.equal(byLabel["大学生（生活費を負担）・高校生・中学生"], 40000);
  assert.equal(byLabel["大学生（負担なし）・高校生・中学生"], 20000);
  const src = read("app/tools/child-allowance/page.tsx");
  assert.match(src, /childAllowanceExampleTable\(\)/);
  assert.doesNotMatch(src, /[0-9]{1,3},000円/);
  assert.doesNotMatch(src, /｜|ざっくり/);
  for (const id of ["what", "third-child", "payment", "example", "faq"]) assert.match(src, new RegExp(`<ToolSection id="${id}"`));
  assert.match(src, /<ToolSection id="faq" title="よくある疑問"/);
  // 支給日の日にちは言い切らない（市区町村で違う）
  assert.doesNotMatch(src, /10日に支給|10日です/);
  assert.match(src, /title: "児童手当はいくら？ 子どもの年齢と人数で12月の支給額を計算"/);
});

test("計算機の登録：CALCULATORS・記事とガイドからの案内・関連の記事", () => {
  const meta = CALCULATORS["child-allowance"];
  assert.equal(meta.href, "/tools/child-allowance");
  assert.equal(meta.checked, "2026-11-25");
  const base = { title: "", tags: [], genreSlug: "public" };
  assert.equal(calculatorForArticle({ ...base, title: "児童手当、12月の支給日は？" }).kind, "child-allowance");
  assert.equal(calculatorForArticle({ ...base, title: "冬のボーナス", tags: ["児童手当"] }), null);
  assert.equal(calculatorForGuide({ tool: "kosodate", title: "児童手当はいくら？月1万円・1万5千円、高校生年代まで" }), "child-allowance");
  const money = load("lib/money-pages.ts");
  assert.ok(money.moneyRowsForTool("/tools/child-allowance").some((row) => row.key === "child-allowance"));
  // 記事の「自分は対象か確かめる」の行き先は変えない
  assert.equal(money.moneyLinkFor({ title: "児童手当の振込日" }).href, "/articles/child-allowance-eligibility-check");
  assert.match(read("components/calc/CalculatorBox.tsx"), /calc\.kind === "child-allowance"\) return <ChildAllowanceCalc \/>/);
  assert.match(read("lib/sitemap.ts"), /"\/tools\/child-allowance"[^\]]*\]\.map\(fixed\)/);
  assert.ok(fs.existsSync(path.join(root, "components/calc/ChildAllowanceCalc.tsx")));
});
