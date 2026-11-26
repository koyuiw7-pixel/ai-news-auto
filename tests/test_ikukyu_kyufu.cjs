const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 育休中にもらえるお金の計算（lib/ikukyu-kyufu.ts・/tools/ikukyu-kyufu。2026-11-26）。Next.js を起動せずに検査する。
// 数字は厚生労働省「育児休業等給付の内容と支給申請手続」2026年8月1日改訂版（https://www.mhlw.go.jp/content/11600000/001461102.pdf）と
// 「令和8年8月1日から支給限度額が変更になります」（https://www.mhlw.go.jp/content/001728499.pdf）。2026-11-26 確認。
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
const k = load("lib/ikukyu-kyufu.ts");
const { CALCULATORS, calculatorForArticle, calculatorForGuide } = load("lib/calculators.ts");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");

test("厚生労働省の上限額・下限額（2026年8月1日〜2027年7月31日）と一致する", () => {
  assert.equal(k.DAILY_WAGE_MAX, 16540);
  assert.equal(k.DAILY_WAGE_MIN, 3203);
  assert.equal(k.MONTHLY_MAX, 496200);
  assert.equal(k.MONTHLY_MIN, 96090);
  const hi = k.ikukyuKyufu({ monthly: 800000, days: 360, shussei: true });
  assert.equal(hi.capped, "max");
  assert.equal(hi.firstMonthly, 332454);
  assert.equal(hi.laterMonthly, 248100);
  assert.equal(hi.shussei, 60205);
  const lo = k.ikukyuKyufu({ monthly: 50000, days: 360, shussei: true });
  assert.equal(lo.capped, "min");
  assert.equal(lo.firstMonthly, 64380);
  assert.equal(lo.laterMonthly, 48045);
  assert.equal(lo.shussei, 11658);
  // 出生時育児休業給付金の28日の上限 310,290円（16,540円×28日×67%）と同じ式
  assert.equal(Math.floor((16540 * 28 * 67) / 100), 310290);
});

test("手引の例：休業開始時賃金日額10,000円（月給30万円）→ 30日で201,000円、上乗せ28日で36,400円", () => {
  const r = k.ikukyuKyufu({ monthly: 300000, days: 30, shussei: true });
  assert.equal(r.daily, 10000);
  assert.equal(r.firstMonthly, 201000);
  assert.equal(r.shussei, 36400);
  assert.equal(r.total, 237400);
});

test("ページの表：月給20万・25万・30万・40万円の最初の6か月の月額", () => {
  const rows = k.ikukyuExampleTable().map(({ monthly, result }) => [monthly, result.firstMonthly, result.laterMonthly, result.shussei]);
  assert.deepEqual(rows, [
    [200000, 134000, 100000, 24266],
    [250000, 167500, 125000, 30333],
    [300000, 201000, 150000, 36400],
    [400000, 268000, 200000, 48533],
  ]);
  const ex = k.ikukyuKyufu(k.IKUKYU_EXAMPLE);
  assert.deepEqual([ex.firstTotal, ex.laterTotal, ex.shussei, ex.total], [1206000, 900000, 36400, 2142400]);
});

test("180日で67%から50%に、上乗せは14日以上で28日まで", () => {
  const r = k.ikukyuKyufu({ monthly: 300000, days: 200, shussei: true });
  assert.equal(r.firstDays, 180);
  assert.equal(r.laterDays, 20);
  assert.equal(r.laterTotal, 100000); // 10,000円×20日×50%
  assert.equal(k.ikukyuKyufu({ monthly: 300000, days: 13, shussei: true }).shussei, 0);
  assert.equal(k.ikukyuKyufu({ monthly: 300000, days: 14, shussei: true }).shussei, 18200); // 手引の例 10,000円×14日×13%
  assert.equal(k.ikukyuKyufu({ monthly: 300000, days: 360, shussei: false }).shussei, 0);
  assert.equal(k.daysJa(360), "12か月");
  assert.equal(k.daysJa(45), "1か月と15日");
});

test("ページ：例の数字は計算で出し、表・FAQ・出典・使わない文字を確かめる", () => {
  const src = read("app/tools/ikukyu-kyufu/page.tsx");
  assert.match(src, /title: "育休中にもらえるお金はいくら？ 月給から育児休業給付金を計算"/);
  assert.match(src, /ikukyuKyufu\(IKUKYU_EXAMPLE\)/);
  assert.match(src, /ikukyuExampleTable\(\)/);
  assert.match(src, /<table/);
  assert.match(src, /"@type": "FAQPage"/);
  assert.match(src, /非課税/);
  assert.match(src, /サイソク編集部の計算/);
  // 例の金額は手で書かない（手引の例の日額10,000円は出典の数字なので除く）
  assert.doesNotMatch(src.replace("10,000円", ""), /[0-9]{1,3},[0-9]{3}円/);
  for (const id of ["what", "example", "faq", "sources", "guides"]) assert.match(src, new RegExp(`<ToolSection id="${id}"`));
  // 広告は育休の記事と同じ話題（childbirth）だけ
  assert.match(src, /r\.key === "childbirth"/);
  for (const rel of ["app/tools/ikukyu-kyufu/page.tsx", "lib/ikukyu-kyufu.ts", "components/calc/IkukyuKyufuCalc.tsx"]) {
    assert.doesNotMatch(read(rel), /｜|ざっくり|人へ/, rel);
  }
  for (const s of Object.values(k.IKUKYU_SOURCES)) assert.match(s.href, /^https:\/\/www\.(mhlw\.go\.jp|nenkin\.go\.jp)\//);
  const calc = read("components/calc/IkukyuKyufuCalc.tsx");
  assert.match(calc, /IKUKYU_EXAMPLE\.monthly/);
  assert.match(calc, /data-ikukyu-next[\s\S]*href="\/tools\/child-allowance"/);
});

test("計算機の登録：CALCULATORS・記事とガイドからの案内・関連の記事・サイトマップ", () => {
  const meta = CALCULATORS["ikukyu-kyufu"];
  assert.equal(meta.href, "/tools/ikukyu-kyufu");
  assert.equal(meta.checked, "2026-11-26");
  const base = { title: "", tags: [], genreSlug: "public" };
  assert.equal(calculatorForArticle({ ...base, title: "育児休業給付金は181日目から50％に" }).kind, "ikukyu-kyufu");
  assert.equal(calculatorForArticle({ ...base, title: "育休給付金、181日目から50%に" }).kind, "ikukyu-kyufu");
  assert.equal(calculatorForArticle({ ...base, title: "男性の育休取得率", tags: ["育児休業"] }), null);
  assert.equal(calculatorForGuide({ tool: "x", title: "育児休業給付金の申請" }), "ikukyu-kyufu");
  const money = load("lib/money-pages.ts");
  const row = money.moneyRowsForTool("/tools/ikukyu-kyufu").find((r) => r.key === "ikukyu-kyufu");
  assert.ok(row);
  for (const slug of row.articles) assert.ok(fs.existsSync(path.join(root, "content/articles", `${slug}.json`)), slug);
  assert.match(read("components/calc/CalculatorBox.tsx"), /calc\.kind === "ikukyu-kyufu"\) return <IkukyuKyufuCalc \/>/);
  assert.match(read("lib/sitemap.ts"), /"\/tools\/ikukyu-kyufu"[^\]]*\]\.map\(fixed\)/);
  assert.match(read("components/Footer.tsx"), /\/tools\/ikukyu-kyufu/);
  assert.match(read("app/choose/page.tsx"), /CALCULATORS\["ikukyu-kyufu"\]/);
  assert.match(read("lib/page-share.ts"), /"ikukyu-kyufu": \{ heading:/);
});

test("受け取るまでの流れ：会社がハローワークへ・4か月の期限・約1週間（厚生労働省の手引 2026-11-27 確認）", () => {
  const g = k.IKUKYU_RECEIVE;
  assert.deepEqual(g.steps.map((s) => s.label), ["誰が", "どこへ", "いつまでに", "いつ入る"]);
  const all = g.steps.map((s) => s.text).join("");
  for (const fact of ["会社が申請", "自分で出す", "ハローワーク", "母子健康手帳の写し", "口座", "出生後休業支援給付金", "同じ申請書", "4か月を過ぎる日がある月の末日", "11月30日", "58日目", "2か月に1回", "約1週間"]) {
    assert.ok(all.includes(fact), fact);
  }
  assert.doesNotMatch(all + g.title, /｜|ざっくり|人へ|→/);
  assert.deepEqual(g.sources, [k.IKUKYU_SOURCES.pamphlet]);
  assert.equal(g.checked, "2026-11-27");
  const calc = read("components/calc/IkukyuKyufuCalc.tsx");
  assert.match(calc, /data-ikukyu-result[\s\S]*data-ikukyu-next[\s\S]*<ReceiveSteps guide=\{IKUKYU_RECEIVE\} \/>/);
  assert.match(read("app/tools/ikukyu-kyufu/page.tsx"), /q: "最初の申請はいつまでですか"/);
});
