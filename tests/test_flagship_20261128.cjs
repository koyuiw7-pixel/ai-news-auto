const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const test = require("node:test");
const ts = require("typescript");

// 特集（/stories/<slug>。lib/flagship.ts・content/flagship/*.json・components/flagship/*）。2026-11-28
// 画面に出す数字はすべて lib/child-allowance.ts の式で出す（こども家庭庁「児童手当制度のご案内」2026-11-28 確認）。
// 事実は出典（公式が先、報道が後）につなぎ、読者の文に「｜」「**」「→」などを使わない。広告の枠は1ページに1つ。
const root = path.resolve(__dirname, "..");
const cache = {};
function load(rel) {
  if (cache[rel]) return cache[rel];
  const file = path.join(root, rel);
  const out = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true },
  }).outputText;
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = Module._nodeModulePaths(path.dirname(file));
  const original = mod.require.bind(mod);
  mod.require = (name) => {
    if (name.startsWith("@/content/")) return JSON.parse(fs.readFileSync(path.join(root, name.slice(2)), "utf8"));
    if (name.startsWith("@/lib/")) return load(`lib/${name.slice(6)}.ts`);
    return original(name);
  };
  mod._compile(out, file);
  cache[rel] = mod.exports;
  return mod.exports;
}
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const ca = load("lib/child-allowance.ts");
const fl = load("lib/flagship.ts");
const cat = (...categories) => categories.map((category) => ({ kind: "category", category }));

test("特集の一覧と URL（/stories/<slug>）。記事と計算ツールから案内する", () => {
  assert.ok(fl.FLAGSHIP_STORIES.length >= 1);
  const story = fl.getFlagship("third-child-1000man");
  assert.ok(story);
  assert.equal(fl.flagshipHref(story.slug), "/stories/third-child-1000man");
  assert.deepEqual(fl.flagshipForArticle("third-child-benefit-proposal"), { href: "/stories/third-child-1000man", title: story.title });
  assert.deepEqual(fl.flagshipForTool("/tools/child-allowance"), { href: "/stories/third-child-1000man", title: story.title });
  for (const s of fl.FLAGSHIP_STORIES) {
    assert.ok(fs.existsSync(path.join(root, "content/articles", `${s.article}.json`)), `記事が無い: ${s.article}`);
    assert.ok(fs.existsSync(path.join(root, "app", s.tool, "page.tsx")), `計算ツールが無い: ${s.tool}`);
    for (const link of s.next) {
      const ok = link.href.startsWith("/articles/") ? fs.existsSync(path.join(root, "content/articles", `${link.href.slice(10)}.json`)) : fs.existsSync(path.join(root, "app", link.href, "page.tsx"));
      assert.ok(ok, `行き先が無い: ${link.href}`);
    }
  }
  // 記事（今までの見た目・ノワール）と計算ツールに案内がある
  assert.match(read("components/noir/noirArticlePage.tsx"), /<FlagshipLink target=\{flagship\}/);
  assert.match(read("app/articles/[slug]/page.tsx"), /<FlagshipLink target=\{flagshipForArticle\(article\.slug\)\}/);
  assert.match(read("app/tools/child-allowance/page.tsx"), /intro=\{<FlagshipLink target=\{flagshipForTool\(meta\.href\)\}/);
});

test("事実はすべて出典につながり、出典は公式が先・報道が後。確かめた日がある", () => {
  for (const story of fl.FLAGSHIP_STORIES) {
    const ids = new Set(story.sources.map((s) => s.id));
    assert.equal(ids.size, story.sources.length, "出典の id が重複");
    const refs = [
      ...story.answer.sources,
      ...story.status.decided.flatMap((x) => x.sources),
      ...story.status.undecided.flatMap((x) => x.sources),
      ...story.proposal.known.flatMap((x) => x.sources),
      ...story.proposal.watch.flatMap((x) => x.sources),
      ...story.proposal.insightSources,
      ...story.checklist.flatMap((x) => x.sources),
    ];
    for (const r of refs) assert.ok(ids.has(r), `出典が無い: ${r}`);
    for (const list of [story.status.decided, story.status.undecided, story.proposal.known, story.proposal.watch, story.checklist]) {
      for (const item of list) assert.ok(item.sources.length > 0, `出典の無い項目: ${JSON.stringify(item).slice(0, 60)}`);
    }
    for (const s of story.sources) {
      assert.match(s.url, /^https:\/\//);
      assert.match(s.checked, /^\d{4}-\d{2}-\d{2}$/);
      assert.ok(["official", "report"].includes(s.kind));
    }
    const ordered = fl.orderedSources(story).map((s) => s.kind);
    assert.deepEqual(ordered, [...ordered].sort((a, b) => (a === b ? 0 : a === "official" ? -1 : 1)), "公式が先");
    // 決まっていないことは決まっていないと書く（提言案は「決まっていません」）
    assert.match(story.answer.lead, /^決まっていません。/);
    assert.ok(story.status.undecided.length > 0);
    // 日付は正直に（公開 ≦ 更新、時点の日付は公開の日）
    assert.ok(new Date(story.publishedAt) <= new Date(story.updatedAt));
    assert.equal(story.asOf, new Date(new Date(story.publishedAt).getTime() + 9 * 3600e3).toISOString().slice(0, 10));
  }
});

test("1000万円の案について、出典に無い金額・日付を作らない", () => {
  const story = fl.getFlagship("third-child-1000man");
  const proposalText = JSON.stringify(story.proposal);
  // 1000万円の内訳（現金〇円・サービス〇円）や、首相への提出の日にちを書かない
  assert.doesNotMatch(proposalText, /\d+月\d+日に(首相|政府)/);
  assert.doesNotMatch(proposalText, /(現金|サービス)[^。]{0,6}\d+万円/);
  assert.match(proposalText, /1000万円規模/);
  assert.match(story.proposal.badge, /決まっていません/);
});

test("画面と FAQ の数字は lib/child-allowance.ts と同じ", () => {
  const A = ca.CHILD_ALLOWANCE_AMOUNTS;
  assert.deepEqual({ ...A }, { under3: 15000, from3: 10000, third: 30000 });
  const story = fl.getFlagship("third-child-1000man");
  const text = JSON.stringify(story);
  assert.match(text, /第3子以降は年齢に関係なく1人月3万円/);
  const faq = story.faq.map((f) => f.a).join("");
  assert.match(faq, /3歳未満が月1万5,000円、3歳から高校生年代までが月1万円/);
  const dec = ca.paymentFor([], { year: 2026, month: 12 });
  assert.match(faq, new RegExp(`2026年12月の支給は${dec.months[0].month}月分と${dec.months[1].month}月分`));
});

test("計算: 次の支給の月・例の家族・これから受け取る合計・第3子のいちばん多い場合", () => {
  const A = ca.CHILD_ALLOWANCE_AMOUNTS;
  assert.deepEqual(ca.nextPaymentMonth({ year: 2026, month: 11 }), { year: 2026, month: 12 });
  assert.deepEqual(ca.nextPaymentMonth({ year: 2026, month: 12 }), { year: 2026, month: 12 });
  assert.deepEqual(ca.nextPaymentMonth({ year: 2027, month: 1 }), { year: 2027, month: 2 });
  assert.deepEqual(ca.tokyoYearMonth(new Date("2026-11-30T15:30:00Z")), { year: 2026, month: 12 });
  // 撮影と同じ「小学生2人と3歳未満」: 12月の支給 100,000円・月 50,000円・1年分 600,000円
  const kids = cat("from3", "from3", "under3");
  const r = ca.childAllowance(kids, ca.nextPaymentMonth({ year: 2026, month: 11 }));
  assert.equal(r.next.amount, 100000);
  assert.equal(r.monthly, 50000);
  assert.equal(r.year.total, 600000);
  assert.deepEqual(r.children.map((c) => [c.rank, c.amount]), [[1, 10000], [2, 10000], [3, 30000]]);
  assert.deepEqual(ca.familyCounts(kids, { year: 2026, month: 11 }), { children: 3, expected: 0, paid: 3, counted: 3, thirdOrLater: 1 });
  assert.deepEqual(ca.familyCounts(cat("olderSupported", "from3"), { year: 2026, month: 11 }), { children: 2, expected: 0, paid: 1, counted: 2, thirdOrLater: 0 });
  assert.deepEqual(ca.familyCounts([{ kind: "birth", year: 2015, month: 4 }, { kind: "birth", year: 2027, month: 3 }], { year: 2026, month: 11 }), { children: 1, expected: 1, paid: 1, counted: 1, thirdOrLater: 0 });
  // 特集の「サイソクの見方」: 2026年12月生まれの第3子は 2027年1月分〜2045年3月分（219か月）×30,000円
  const max = ca.thirdChildMaxTotal({ year: 2026, month: 12 });
  assert.equal(max.months, 219);
  assert.equal(max.total, 219 * A.third);
  assert.deepEqual(max.last, { year: 2045, month: 3 });
  // これから受け取る合計（生まれた年月）: 2026年10月生まれ1人なら、11月分から3歳の誕生月（2029年10月）まで 15,000円、
  // その後 2045年3月分まで 10,000円
  const one = ca.remainingTotal([{ kind: "birth", year: 2026, month: 10 }], { year: 2026, month: 11 });
  const under3Months = (2029 - 2026) * 12 + (10 - 11) + 1; // 2026-11..2029-10
  const from3Months = (2045 - 2029) * 12 + (3 - 10); // 2029-11..2045-03
  assert.equal(one.total, under3Months * A.under3 + from3Months * A.from3);
  assert.deepEqual(one.last, { year: 2045, month: 3 });
  // まだ生まれていない子は、生まれた月の次の月から
  const due = ca.remainingTotal([{ kind: "birth", year: 2027, month: 3 }], { year: 2026, month: 11 }, 6);
  assert.equal(due.total, A.under3); // 2027年4月分の1か月だけ（6か月の範囲）
});

test("やることリスト: 出生日の次の日から15日以内の期限の日付", () => {
  const { birthDeadline } = load("lib/flagship-date.ts");
  assert.deepEqual(birthDeadline("2026-11-28"), { iso: "2026-12-13", label: "2026年12月13日（日）" });
  assert.equal(birthDeadline("2026-12-25").iso, "2027-01-09");
  assert.equal(birthDeadline("2027-02-20").iso, "2027-03-07");
  assert.equal(birthDeadline("あ"), null);
  const story = fl.getFlagship("third-child-1000man");
  const birth = story.checklist.filter((c) => c.birthDeadline);
  assert.equal(birth.length, 1);
  assert.match(birth[0].deadline, /出生日の次の日から15日以内/);
});

const FILES = ["content/flagship/third-child-1000man.json", "components/flagship/FlagshipStoryView.tsx", "components/flagship/FamilyBuilder.tsx", "components/flagship/Checklist.tsx", "components/flagship/ShareCard.tsx", "components/flagship/FlagshipLink.tsx", "app/stories/[slug]/page.tsx"];
const code = (rel) => read(rel).split("\n").filter((line) => !/^\s*(\/\/|\*|\/\*)/.test(line)).join("\n");

test("読者の文の決まり: 「｜」「**」「→」「↗」「ざっくり」「〜の人へ」「しましょう」を使わない。黄色を使わない", () => {
  for (const rel of FILES) {
    const src = code(rel);
    for (const [re, name] of [[/｜/, "｜"], [/\*\*/, "**"], [/→/, "→"], [/↗/, "↗"], [/ざっくり/, "ざっくり"], [/の人へ/, "〜の人へ"], [/しましょう/, "しましょう"]]) {
      assert.doesNotMatch(src, re, `${rel}: ${name}`);
    }
  }
  const css = read("components/flagship/flagship.css");
  assert.doesNotMatch(css, /yellow|gold|amber/i, "黄色を使わない");
  // 色の値（#rrggbb）に黄色・砂色（色相 35〜70°で色の濃いもの）が無い
  for (const [hex] of css.matchAll(/#[0-9a-f]{6}\b/gi)) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    if (max - min < 0.15) continue;
    const h = max === r ? ((g - b) / (max - min)) * 60 : max === g ? (2 + (b - r) / (max - min)) * 60 : (4 + (r - g) / (max - min)) * 60;
    const hue = (h + 360) % 360;
    assert.ok(hue < 35 || hue > 70, `黄色: ${hex}`);
  }
  assert.match(css, /prefers-reduced-motion: reduce/, "動きを減らす設定");
});

test("広告の枠は1ページに1つ（台帳 W10）。計算ツールと同じ A/B の描き分け", () => {
  const page = code("app/stories/[slug]/page.tsx");
  assert.equal((page.match(/<ActionAd\b/g) ?? []).length, 1);
  assert.match(page, /pos=\{FLAGSHIP_AD_POS\}/);
  for (const rel of ["components/flagship/FlagshipStoryView.tsx", "components/flagship/FamilyBuilder.tsx", "components/flagship/Checklist.tsx", "components/flagship/ShareCard.tsx", "components/flagship/FlagshipLink.tsx"]) {
    const src = code(rel);
    assert.doesNotMatch(src, /ActionAd|AffiliateBox|CompareOffers|data-aff-pos|rel="sponsored|AdSlot/, `${rel} に広告を足さない`);
  }
  // 広告の枠は FamilyBuilder の中で1回だけ描く
  assert.equal((code("components/flagship/FamilyBuilder.tsx").match(/\{adSlot\}/g) ?? []).length, 1);
  assert.equal(load("lib/flagship-pos.ts").FLAGSHIP_AD_POS, "flagship-result");
  assert.doesNotMatch(load("lib/flagship-pos.ts").FLAGSHIP_AD_POS, /-\d+$/);
  assert.match(read("components/ActionAd.tsx"), /pos === "tool-result" \|\| pos === FLAGSHIP_AD_POS \? toolKindFor/);
});

test("検索・AIの答え向け: 問いと答えの題名、最初の文が答え、NewsArticle・FAQPage・canonical・サイトマップ", () => {
  const story = fl.getFlagship("third-child-1000man");
  assert.match(story.title, /？/);
  const ld = read("lib/flagship-jsonld.ts");
  assert.match(ld, /"@type": "NewsArticle"/);
  assert.match(ld, /faqPageJsonLd\(story\.faq\)/);
  assert.match(ld, /datePublished: story\.publishedAt/);
  assert.match(ld, /dateModified: story\.updatedAt/);
  assert.match(read("app/stories/[slug]/page.tsx"), /alternates: \{ canonical: url \}/);
  assert.match(read("app/stories/[slug]/page.tsx"), /export const dynamicParams = false;/);
  assert.match(read("components/flagship/FlagshipStoryView.tsx"), /story\.faq\.map/, "FAQ はページに見せる");
  assert.match(read("lib/sitemap.ts"), /FLAGSHIP_STORIES\.map/);
  assert.match(read("lib/page-share-items.ts"), /FLAGSHIP_STORIES\.map\(\(s\) => `\$\{PREFIX\.story\}/);
  assert.ok(story.share.heading.length <= 24);
});

test("シェアの画像には人数と金額だけ（生まれた年月を入れない）。画像は端末の中で作る", () => {
  const card = code("components/flagship/ShareCard.tsx");
  assert.doesNotMatch(card, /fetch\(|sendBeacon|XMLHttpRequest/);
  const builder = code("components/flagship/FamilyBuilder.tsx");
  const share = builder.slice(builder.indexOf("<ShareCard"), builder.indexOf("/>", builder.indexOf("<ShareCard")));
  assert.doesNotMatch(share, /kid\.year|kid\.month|birth/);
  assert.doesNotMatch(builder, /localStorage|fetch\(/, "入力を保存・送信しない");
});
