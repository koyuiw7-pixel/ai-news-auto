const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

// 決まった欄（なるほど・不安Q&A・判断ガイド・よくある質問）が、記事の結論（リード・要点）の言い直しだけなら出さない（2026-11-25 AdSense の点検）。
// 記事のデータは消さず、画面に出す前（lib/depth.ts の depthOf・記事ページの articleFaq）で外す。基準は厳しめ（lib/repeat-filter.ts）。
const root = path.resolve(__dirname, "..");
const { buildSync } = require("esbuild");

function load(entry) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "saisoku-repeat-"));
  const outfile = path.join(dir, "out.cjs");
  buildSync({
    entryPoints: [path.join(root, entry)],
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    tsconfig: path.join(root, "tsconfig.json"),
    logLevel: "error",
  });
  try {
    return require(outfile);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

const rf = load("lib/repeat-filter.ts");
const { depthOf } = load("lib/depth.ts");

const lede = "くら寿司では2026年11月27日から、寿司など22商品が10〜30円値上がりします。";
const highlights = ["値下げの対象には、純赤だしや純味噌汁、デザート、ドリンクが入っています。"];

test("リード・要点とほぼ同じ文は「新しい情報なし」。少しでも違う情報がある文は残す", () => {
  const refs = rf.leadRefs({ lede, highlights });
  // 句読点・太字・空白だけの違い
  assert.equal(rf.addsNothing("くら寿司では、2026年11月27日から寿司など22商品が**10〜30円**値上がりします", refs), true);
  // 新しい事実（値下げ幅）がある
  assert.equal(rf.addsNothing("値下げは34商品で、値下げ幅は10〜70円です。", refs), false);
  // 同じ話題でも別の中身（対象の商品名）
  assert.equal(rf.addsNothing("値上げの対象は、熟成まぐろ、サーモン、甘えび、真いわしなどです。", refs), false);
  // 空・短すぎる
  assert.equal(rf.addsNothing("", refs), true);
  assert.equal(rf.addsNothing("はい。", refs), true);
  assert.equal(rf.tooShort("対象です。"), true);
});

test("depthOf: なるほど・不安Q&A・判断ガイドから、リードの言い直しだけの項目を外す。データは消さない", () => {
  const src = "https://www.kurasushi.co.jp/upload/261124release.pdf";
  const article = {
    title: "くら寿司の価格改定",
    lede,
    highlights,
    insight: [
      { text: "くら寿司では2026年11月27日から寿司など22商品が10〜30円値上がりします。", source: src },
      { text: "値下げ対象には「特製ガリ」や「ツナサラダ」も含まれます。", source: src },
    ],
    worries: [
      { q: "いつから？", a: "くら寿司では2026年11月27日から、寿司など22商品が10〜30円値上がりします。", source: src },
      { q: "汁物は？", a: "純赤だしと純味噌汁は値下げの対象です。", source: src },
      { q: "お酒は？", a: "スーパードライ（生）やハイボールも値下げの対象です。", source: src },
    ],
    decisionGuide: [
      { question: "どうする？", situation: "いつもの寿司が対象", recommend: "価格を見直す", reason: "くら寿司では2026年11月27日から、寿司など22商品が10〜30円値上がりします。", source: src },
      { question: "どうする？", situation: "汁物をよく頼む", recommend: "値下げ一覧を見る", reason: "純赤だしなど34商品は10〜70円下がります。", source: src },
    ],
  };
  const before = JSON.stringify(article);
  const d = depthOf(article);
  assert.deepEqual(d.insight.map((x) => x.text), ["値下げ対象には「特製ガリ」や「ツナサラダ」も含まれます。"]);
  assert.deepEqual(d.worries.map((x) => x.q), ["汁物は？", "お酒は？"]);
  assert.deepEqual(d.guide.flatMap((g) => g.rows.map((r) => r.situation)), ["汁物をよく頼む"]);
  assert.equal(JSON.stringify(article), before, "記事のデータを書き換えない");

  // 言い直しを外して2つ未満になった不安Q&Aは、欄ごと出さない（今までの決まり）
  const one = depthOf({ ...article, worries: article.worries.slice(0, 2) });
  assert.deepEqual(one.worries, []);
});

test("記事ページのよくある質問も同じ決まりで外す（答えがリード・要点の言い直しだけの問い）", () => {
  const src = fs.readFileSync(path.join(root, "app/articles/[slug]/page.tsx"), "utf8");
  assert.match(src, /addsNothing\(row\.a, leadRefs\(article\)\)/);
});

test("実データ: 外れる項目はごく少数（基準を厳しめに保つ。まとまって消える欄が出ない）", () => {
  const dir = path.join(root, "content/articles");
  let items = 0;
  let dropped = 0;
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    let a;
    try {
      a = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
    } catch {
      continue;
    }
    const refs = rf.leadRefs(a);
    for (const t of [...(a.insight ?? []).map((x) => x?.text), ...(a.worries ?? []).map((x) => x?.a), ...(a.faq ?? []).map((x) => x?.a)]) {
      if (!t) continue;
      items++;
      if (rf.addsNothing(t, refs)) dropped++;
    }
  }
  assert.ok(items > 0);
  assert.ok(dropped / items < 0.02, `外れる項目が多すぎる（${dropped}/${items}）。基準がゆるくなっていないか確かめる`);
});
