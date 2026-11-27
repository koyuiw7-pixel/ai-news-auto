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
  assert.match(css, /:root\[data-adv="b"\] \.tool-flow > \.tool-ad-slot \{\s*order: -1;/);
  assert.doesNotMatch(css.slice(css.indexOf(".tad-link")), /#f[0-9a-f]{2}[0-9a-f]{0,3}0\b|yellow|#ff[cd]/i, "黄色を使わない");
  const page = read("components/calc/ToolPage.tsx");
  assert.match(page, /className="tool-flow flex flex-col"/);
  const action = read("components/ActionAd.tsx");
  assert.match(action, /a=\{<div className="tad-a" data-tool-ad="a">/);
  assert.match(read("app/layout.tsx"), /<AdSeenTracker \/>/);
});

// オーナーのルール W10（2026-11-03）「同じ広告の枠は1ページに1つまで（見えていない方も数える）」。
// 2026-11-27: A と B を両方 HTML に入れて CSS で隠したら、計算ツールの全8ページで tool-result の枠が2つになった（scripts/ui_check.mjs 6b）
test("結果の下の PR は A か B の片方だけを描く（同じ枠は1ページに1つ。隠した方を HTML に入れない）", () => {
  const action = read("components/ActionAd.tsx");
  const tail = action.slice(action.indexOf('const kind = pos === "tool-result"'));
  assert.match(tail, /<ToolAdSlot\s+a=\{/);
  assert.doesNotMatch(tail.replace(/<ToolAdSlot[\s\S]*?\/>\s*\);/, ""), /<ToolAdCard|tad-a/, "ToolAdSlot の外に A・B を置かない");
  const slot = read("components/ToolAdSlot.tsx");
  assert.match(slot, /^"use client";/);
  assert.match(slot, /variant === "b" \? b : variant === "a" \? a : null/, "選ばれた方だけ（決まる前は空）");
  assert.match(slot, /useSyncExternalStore\(noop, clientVariant, serverVariant\)/);
  assert.doesNotMatch(slot, /data-aff-pos=/, "空の枠には置き場所の印を付けない");
  const css = read("app/globals.css");
  assert.doesNotMatch(css, /\.tad-[ab][^{]*\{\s*display: none/, "CSS で隠す方式に戻さない");
  assert.match(css, /\.tool-ad-slot:empty \{\s*min-height: \d+px;/, "描くまでの高さを先に取る（画面のずれ）");
  assert.match(css, /:root\[data-adv="b"\] \.tool-ad-slot:empty \{\s*min-height: \d+px;/);
});

test("描き分けの部品: A でも B でも tool-result の枠は1つだけ描き、サーバーの HTML（決まる前）は空の枠だけ", () => {
  const { renderToStaticMarkup } = require("react-dom/server");
  // 描き分けの部品を、A・B それぞれに固定して描く（ブラウザの <html data-adv> の代わり）
  const React = require("react");
  for (const adv of ["a", "b"]) {
    const slotSrc = ts.transpileModule(read("components/ToolAdSlot.tsx"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
    const mod = { exports: {} };
    const fakeReact = { ...React, useSyncExternalStore: () => adv, useEffect: () => {} };
    new Function("module", "exports", "require", slotSrc)(mod, mod.exports, (n) => (n === "react" ? fakeReact : n === "@/lib/ad-seen" ? { AD_SLOT_EVENT: "x" } : require(n)));
    const Slot = mod.exports.default;
    const a = React.createElement("div", { className: "tad-a" }, React.createElement("aside", { "data-aff-pos": "tool-result" }));
    const b = React.createElement("aside", { "data-aff-pos": "tool-result", className: "tad-b" });
    const html = renderToStaticMarkup(React.createElement(Slot, { a, b }));
    assert.equal((html.match(/data-aff-pos="tool-result"/g) ?? []).length, 1, adv);
    assert.match(html, adv === "a" ? /tad-a/ : /tad-b/);
  }
  // サーバーの HTML（決まる前）は空の枠だけ
  const slotSrc = ts.transpileModule(read("components/ToolAdSlot.tsx"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", "require", slotSrc)(mod, mod.exports, (n) => (n === "@/lib/ad-seen" ? { AD_SLOT_EVENT: "x" } : require(n)));
  const html = renderToStaticMarkup(React.createElement(mod.exports.default, { a: React.createElement("aside", { "data-aff-pos": "tool-result" }), b: React.createElement("aside", { "data-aff-pos": "tool-result" }) }));
  assert.equal(html, '<div class="tool-ad-slot" data-tool-ad-slot=""></div>');
});
