const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

// 台帳 W41（2026-11-11）: 得のカードの A/B（1 = 結果を先に見せる、2 = 比べて選ぶ）。表示は「PR」の札だけ・高さ 260px 以内・ボタンは1つ
const root = path.resolve(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(root, f), "utf8");

function loadAb() {
  const out = ts.transpileModule(read("lib/ad-ab.ts"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", "require", out)(mod, mod.exports, require);
  return mod.exports;
}
const ab = loadAb();
const src = (url) => ({ name: "x", url, checkedAt: "2026-11-10" });
const benefit = (chips, headline) => ({ headline, chips: chips.map(([label, value, sub]) => ({ label, value, sub, source: src("https://example.com/") })), points: [], sources: [src("https://example.com/")] });

test("[W41] ふるさと納税は総務省の目安表の値（年収500万円・独身又は共働き 61,000円）をそのまま使い、所得割・税率の言葉を使わない", () => {
  assert.equal(ab.SOUMU_500.single, 61000);
  assert.equal(ab.SOUMU_500.couple, 49000);
  const card = ab.abCardFor({ key: "rakuten-furusato", kind: "partner", name: "楽天ふるさと納税", url: "https://px.a8.net/x", shop: "", cta: "", benefit: benefit([["自己負担", "2,000円"]], "子育て世帯のふるさと納税") });
  assert.equal(card.kind, "furusato");
  assert.equal(card.who, "年収500万円・共働き・子どもは中学生まで");
  assert.deepEqual(card.result.number, { pre: "約", num: "6.1", unit: "万円" });
  assert.equal(card.result.after, "まで寄付して、負担は2,000円");
  assert.equal(card.cta, "楽天ふるさと納税で返礼品を探す");
  assert.equal(card.tool.href, "/tools/furusato-limit");
  assert.match(card.note.arm1, /総務省「全額控除されるふるさと納税額（年間上限）の目安」（11\/11確認）/);
  const text = JSON.stringify(card);
  assert.doesNotMatch(text, /所得割|税率|ポイント/);
  assert.equal(card.compare.bars[1].value, "約5.9万円");
});

test("[W41] マネーフォワードは税込 11,880円と12月の料金改定を書く。見出しに専門の言葉を使わない", () => {
  const card = ab.abCardFor({ key: "mf-kakutei", kind: "partner", name: "マネーフォワード クラウド確定申告", url: "https://px.a8.net/y", shop: "", cta: "", benefit: benefit([["料金", "年11,880円〜", "税込"]]) });
  assert.equal(card.kind, "mf");
  assert.doesNotMatch(card.who, /青色|控除|65万/);
  assert.match(card.result.line2, /年11,880円（税込）/);
  assert.match(card.note.arm1, /12月に料金改定予定/);
  assert.equal(ab.BLUE_65_SAVING, 131365);
  const data = JSON.parse(read("content/ad_benefits.json"));
  assert.equal(data.offers["mf-kakutei"].chips[0].value, "年11,880円〜");
  assert.match(data.offers["mf-kakutei"].chips[0].sub, /税込/);
});

test("[W41] 数字の無い商品は A/B に入れない（今までのカード）", () => {
  assert.equal(ab.abCardFor({ key: "x", kind: "partner", name: "X", url: "u", shop: "", cta: "", benefit: { chips: [], points: ["a"], sources: [] } }), undefined);
  assert.equal(ab.abCardFor({ key: "b", kind: "book", name: "本", url: "u", shop: "", cta: "" }), undefined);
  assert.deepEqual(ab.splitNumber("月495円〜"), { pre: "月", num: "495", unit: "円〜" });
});

test("[W41] 囲み: 両方の arm を HTML に入れ、data-ab-arm・ボタン1つ・PR の札だけ。arm は描画前に決める（?ab=1/2 で固定）", () => {
  const box = read("components/rail/AbBox.tsx");
  assert.match(box, /data-ab-arm=\{arm\}/);
  assert.match(box, /data-aff-pos=\{pos\}/);
  assert.equal((box.match(/className="pr-cta abx-cta"/g) || []).length, 1, "ボタンは1つ");
  assert.match(box, /<PrTag \/>/);
  const code = box.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/^\s*\/\/.*$/gm, "");
  assert.doesNotMatch(code, /紹介料|プロモーション|サイトが開きます|サイトへ移動します|広告・/);
  const layout = read("app/layout.tsx");
  assert.match(layout, /saisoku:abc/);
  assert.match(layout, /\[\?&\]ab=\(\[12\]\)/);
  const css = read("app/globals.css");
  assert.match(css, /:root:not\(\[data-abc="1"\]\) \.abx-arm-1,\n:root\[data-abc="1"\] \.abx-arm-2 \{\n  display: none;/);
  // 2026-11-11 リーダーの確認: 決まった高さで空白を作らない（高さは中身で決まり、arm は描画前に決まるので画面はずれない）・小さな文字は「…」で切らない
  assert.doesNotMatch(css, /\.abx-arm \{[^}]*min-height/);
  assert.doesNotMatch(css, /\.abx-note \{[^}]*line-clamp/);
  assert.match(css, /\.abx-link \{[^}]*min-height: 44px/);
  assert.match(css, /\.abx-cta \{[^}]*min-height: 48px/);
  for (const f of ["components/rail/RailRanking.tsx", "components/ActionAd.tsx"]) assert.match(read(f), /<AbBox/);
});

test("[W41] 計測: クリックに arm、表示（枠が半分以上見えた）に arm と置き場所。集計は arm ごとのクリック率", () => {
  assert.match(read("components/AffClickTracker.tsx"), /closest\("\[data-ab-arm\]"\)/);
  const aff = read("cloudflare/aff.ts");
  assert.match(aff, /body\?\.arm === "1" \|\| body\?\.arm === "2"/);
  assert.match(aff, /byArm:/);
  assert.match(read("components/ReadingBeacon.tsx"), /el.querySelector\("\[data-ab-arm\]"\)/);
  assert.match(read("cloudflare/reading.ts"), /abSeen/);
  assert.match(read("scripts/aff_stats.py"), /def arm_summary/);
  assert.match(read("docs/owner_rules.md"), /^\| W41 \| \*\*2026-11-11/m);
});

test("[W41] lib/reading.ts: b と k は省略でき、正しい値だけ受け取る", () => {
  const out = ts.transpileModule(read("lib/reading.ts").replace(/^import .*$/m, "const INFLOW_SOURCES = ['google']; const validPageKey = () => true;"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", out)(mod, mod.exports);
  const base = { p: "a", s: "google", d: 50, t: 10, n: false, a: ["action-ad"], x: "" };
  assert.equal(mod.exports.parseReading(base).b, undefined);
  assert.deepEqual(mod.exports.parseReading({ ...base, b: "1", k: ["action-ad", "action-ad"] }).k, ["action-ad"]);
  assert.equal(mod.exports.parseReading({ ...base, b: "3", k: ["action-ad"] }), null);
  assert.equal(mod.exports.parseReading({ ...base, b: "2", k: ["BAD POS"] }), null);
});

test("[W41] ボタンの下のリンクは何のリンクか分かる言葉（au PAYでも探せる・ITものづくり教室なら：LITALICOワンダー）", () => {
  assert.equal(ab.altLinkText({ key: "aupay-furusato", name: "au PAY ふるさと納税", label: "ふるさと納税" }, { key: "rakuten-furusato" }), "au PAYでも探せる");
  assert.equal(ab.altLinkText({ key: "yayoi-kakutei", name: "弥生のクラウド確定申告ソフト", label: "個人事業主の確定申告" }, { key: "mf-kakutei" }), "弥生と比べる");
  assert.equal(ab.altLinkText({ key: "litalico", name: "LITALICOワンダー", label: "ITものづくり教室" }, { key: "digitane" }), "ITものづくり教室なら：LITALICOワンダー");
  assert.equal(ab.altLinkText({ key: "x", name: "X" }, { key: "digitane" }), undefined);
});

test("[W41] 見出しが大きな数字をくり返すときは「誰向けか」の1行（デジタネ: 子どもの習いごとを探している方）", () => {
  const b = { headline: "子どもの習いごとを、まず14日間の無料で試す", who: "子どもの習いごとを探している方", chips: [{ label: "無料体験", value: "14日間", source: src("https://example.com/") }], points: [], sources: [src("https://example.com/")] };
  const card = ab.abCardFor({ key: "digitane", kind: "partner", name: "デジタネ", url: "u", shop: "", cta: "", benefit: b });
  assert.equal(card.who, "子どもの習いごとを探している方");
  const data = JSON.parse(read("content/ad_benefits.json"));
  assert.equal(data.offers.digitane.who, "子どもの習いごとを探している方");
});
