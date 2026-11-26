const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

// 2026-11-27 オーナー「広告の選定は悪くはないと思ったけど、それ以上に配置と見た目が魅力０だった」:
// 計算ツールの結果の下の PR を A/B（<html data-adv>）。A = 今までの囲み、B = 同じ提携先の新しい見た目（lib/tool-ad.ts・components/ToolAdCard.tsx）
const root = path.resolve(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(root, f), "utf8");

function loadToolAd() {
  const out = ts.transpileModule(read("lib/tool-ad.ts"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const mod = { exports: {} };
  const stub = (name) => (name === "@/lib/child-allowance" ? { CHILD_ALLOWANCE_NEXT_PAYMENT: { year: 2026, month: 12 } } : require(name));
  new Function("module", "exports", "require", out)(mod, mod.exports, stub);
  return mod.exports;
}
const toolAd = loadToolAd();
const offers = JSON.parse(read("content/offers.json"));
const benefits = JSON.parse(read("content/ad_benefits.json"));

// 計算ツール → 結果の下の話題（content/offers.json の actionAds）。A の囲みの1つ目の提携先が B にも出る
const TOOL_RULE = {
  "child-allowance": "kids",
  "ikukyu-kyufu": "childbirth",
  "pension-support-benefit": "mobile",
  "furusato-limit": "furusato",
  "bonus-tedori": "furusato",
  "defense-tax": "furusato",
  "denki-gas-discount": "energy",
  "kogaku-ryoyohi": "tax",
};

test("どの計算ツールも、A と同じ1つ目の提携先に B の決めた文がある（提携先は変えない）", () => {
  for (const [tool, rule] of Object.entries(TOOL_RULE)) {
    const first = offers.actionAds.find((r) => r.key === rule).partners[0];
    assert.ok(toolAd.TOOL_AD_COPY[`${tool}:${first}`], `${tool}:${first}`);
  }
  assert.match(toolAd.TOOL_AD_COPY["child-allowance:digitane"].headline, /^12月の児童手当/);
});

test("B の文: 矢印・出典・景品表示法で使えない言葉なし。見出し・1行・ボタンは短く、ボタンは押した先で何ができるか", () => {
  for (const [key, copy] of Object.entries(toolAd.TOOL_AD_COPY)) {
    const all = `${copy.headline}${copy.line}${copy.cta}`;
    assert.doesNotMatch(all, /[→⇒➡▶»>]|出典|確認）|最安|必ず|絶対|No\.?1|一番|日本一/, key);
    assert.doesNotMatch(all, /｜/, key);
    assert.ok(copy.headline.length <= 30, `${key} 見出し ${copy.headline.length}`);
    assert.ok(copy.line.length <= 45, `${key} 1行 ${copy.line.length}`);
    assert.match(copy.cta, /見る|探す|相談する/, key);
    const partner = key.split(":")[1];
    assert.ok(offers.partners[partner], `${key} の提携先が offers.json に無い`);
  }
});

test("B の1行の数字は、offers.json・ad_benefits.json の確認済みの事実（または総務省の 2,000円・12月31日）だけ", () => {
  const allowed = new Set(["2,000", "12", "31"]);
  for (const [key, copy] of Object.entries(toolAd.TOOL_AD_COPY)) {
    const partner = key.split(":")[1];
    const facts = JSON.stringify(offers.partners[partner]) + JSON.stringify(benefits.offers[partner] ?? {});
    for (const n of `${copy.line}${copy.cta}`.match(/\d[\d,]*/g) ?? []) {
      assert.ok(allowed.has(n) || facts.includes(n), `${key}: ${n} の出どころが無い`);
    }
  }
});

test("決めた文の無い提携先は、商品の公式の言葉（pitch）から作る。言葉が無ければ B を出さない", () => {
  const copy = toolAd.toolAdCopy("child-allowance", { key: "x", kind: "partner", name: "テスト（仮）", url: "https://example.invalid/", shop: "", cta: "公式サイトで見る", pitch: { gain: "試せる", merits: ["無料体験あり"] } });
  assert.deepEqual(copy, { headline: "試せる", line: "無料体験あり。", cta: "テストで料金と条件を見る" });
  assert.equal(toolAd.toolAdCopy("child-allowance", { key: "y", kind: "partner", name: "n", url: "", shop: "", cta: "" }), undefined);
  assert.equal(toolAd.toolKindFor(undefined, "kids"), "child-allowance");
  assert.equal(toolAd.toolKindFor(undefined, "furusato"), undefined, "ふるさと納税はページで指定（上限額・ボーナス・防衛特別所得税）");
  assert.equal(toolAd.toolKindFor("bonus-tedori", "furusato"), "bonus-tedori");
});

test("計算ツールのページ: 結果の下の PR があり、計算ツールが決まる（指定か話題から）", () => {
  for (const tool of Object.keys(TOOL_RULE)) {
    const src = read(`app/tools/${tool}/page.tsx`);
    assert.match(src, /<ActionAd [^>]*pos=\{GUIDE_AD_POS\.tool\}/, tool);
    const explicit = new RegExp(`tool="${tool}"`).test(src);
    const inferred = ["child-allowance", "ikukyu-kyufu", "pension-support-benefit", "denki-gas-discount"].includes(tool);
    assert.ok(explicit || inferred, tool);
  }
});

test("B の囲み: 小さな「PR」の札・rel=sponsored・ボタン1つ・出典の行なし。A/B は data-adv で半々、B は結果のすぐ下", () => {
  const card = read("components/ToolAdCard.tsx").split("export default")[1];
  assert.match(card, /<PrTag \/>/);
  assert.match(card, /rel=\{AFFILIATE_REL\}/);
  assert.equal((card.match(/<a /g) ?? []).length, 1, "リンクは1つ（囲み全体）");
  assert.equal((card.match(/tad-cta/g) ?? []).length, 1, "ボタンは1つ");
  assert.match(card, /data-aff-pos=\{pos\}/);
  assert.match(card, /data-ad-ab=""/);
  assert.doesNotMatch(card, /sourceLine|出典|OtherSites/);
  const css = read("app/globals.css");
  assert.match(css, /:root\[data-adv="b"\] \.tad-a,\s*:root:not\(\[data-adv="b"\]\) \.tad-b \{\s*display: none !important;/);
  assert.match(css, /:root\[data-adv="b"\] \.tool-flow > \.tad-b \{\s*order: -1;/);
  assert.doesNotMatch(css.slice(css.indexOf(".tad-link")), /#f[0-9a-f]{2}[0-9a-f]{0,3}0\b|yellow|#ff[cd]/i, "黄色を使わない");
  const page = read("components/calc/ToolPage.tsx");
  assert.match(page, /className="tool-flow flex flex-col"/);
  const action = read("components/ActionAd.tsx");
  assert.match(action, /className="tad-a" data-tool-ad="a"/);
  assert.match(read("app/layout.tsx"), /<AdSeenTracker \/>/);
});
