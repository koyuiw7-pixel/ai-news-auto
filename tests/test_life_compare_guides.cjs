const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

// 暮らしとお金の比較ページ5本（content/buying-guides/*.json、M5）。
// 提携リンクは offers.json の承認済みの提携先だけ・価格は公式の出典と確認日つき・検索に出さない設定はそのまま、を確かめる。
const root = path.resolve(__dirname, "..");
const SLUGS = ["kakuyasu-sim", "hikari", "denki-gas", "hoken-soudan", "furusato-sites"];
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const guides = Object.fromEntries(SLUGS.map((slug) => [slug, JSON.parse(read(`content/buying-guides/${slug}.json`))]));
const offers = JSON.parse(read("content/offers.json")).partners;
const affiliates = JSON.parse(read("affiliate_links.json"));

// パッケージで決めた、ページごとに PR にしてよい提携先
const ALLOWED_PARTNERS = {
  "kakuyasu-sim": ["bb-excite"],
  hikari: ["gmo-hikari", "biglobe-hikari", "biglobe-hikari-plus", "gmo-home-wifi", "gmo-wimax", "biglobe-wimax"],
  "denki-gas": ["elpio", "enepi"],
  "hoken-soudan": ["bang-kasai"],
  "furusato-sites": ["furusato-honpo", "rakuten-furusato", "aupay-furusato"],
};

function strings(value, out = []) {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach((v) => strings(v, out));
  else if (value && typeof value === "object") Object.values(value).forEach((v) => strings(v, out));
  return out;
}

test("5本とも新形式で、slug とファイル名が合い、LIFE_COMPARE_SLUGS に並ぶ", () => {
  const lib = read("lib/buying-guides.ts");
  const listed = /LIFE_COMPARE_SLUGS = \[([^\]]*)\]/.exec(lib);
  assert.ok(listed, "LIFE_COMPARE_SLUGS が見つからない");
  assert.deepEqual(listed[1].match(/"[^"]+"/g).map((s) => s.slice(1, -1)), SLUGS);
  for (const slug of SLUGS) {
    const g = guides[slug];
    assert.equal(g.slug, slug);
    assert.equal(g.schemaVersion, 2, slug);
    assert.ok(g.products.length >= 2, `${slug}: 商品が2つ未満だと表示されない`);
    assert.ok((g.fitTable ?? []).length >= 4, `${slug}: 向いている人・向いていない人の表`);
    assert.ok(g.fitTable.some((r) => r.fit === "suits") && g.fitTable.some((r) => r.fit === "not"), slug);
    for (const row of g.fitTable) {
      assert.ok(row.situation && row.recommendation && row.reason, `${slug}: 表の行が欠けている`);
      assert.match(row.source.url, /^https:\/\//, `${slug}: 表の出典`);
    }
    assert.ok((g.officialGuidance ?? []).length >= 1, `${slug}: 公的機関の案内`);
    for (const link of g.officialGuidance) assert.match(link.url, /^https:\/\/www\.(soumu|enecho\.meti|fsa|kokusen|seiho|sonpo|jili)\.(go|or)\.jp\//, `${slug}: ${link.url}`);
    // 公開日・更新日は作った日の実際の時刻（未来や空にしない）
    for (const key of ["publishedAt", "updatedAt", "priceCheckedAt"]) {
      assert.ok(Date.parse(g[key]) <= Date.now(), `${slug}.${key}`);
    }
  }
});

test("PR の商品は承認済みの提携先だけで、offers.json と affiliate_links.json にリンクがある", () => {
  for (const slug of SLUGS) {
    for (const p of guides[slug].products) {
      if (!p.partner) continue;
      assert.ok(ALLOWED_PARTNERS[slug].includes(p.partner), `${slug}: ${p.partner} はこのページの PR に入れない`);
      const partner = offers[p.partner];
      assert.ok(partner, `${p.partner} が offers.json にない`);
      assert.ok(!partner.hidden && !partner.activeUntil, `${p.partner} は表示できない`);
      const link = partner.link ?? affiliates[partner.program]?.url;
      assert.match(link ?? "", /^https:\/\/(px|rpx)\.a8\.net\//, `${p.partner} のリンク`);
      assert.ok(affiliates[partner.program]?.url, `${p.partner} が affiliate_links.json にない`);
    }
  }
});

test("価格には公式の出典と確認日があり、提携していない商品に広告のリンクを付けない", () => {
  for (const slug of SLUGS) {
    for (const p of guides[slug].products) {
      const where = `${slug}/${p.id ?? p.partner}`;
      assert.equal(p.priceSource?.type, "official", where);
      assert.match(p.priceSource.url, /^https:\/\//, where);
      assert.ok(!Number.isNaN(Date.parse(p.priceSource.checkedAt)), where);
      if (p.partner) continue;
      assert.ok(p.id && p.name && p.officialUrl, `${where}: 提携していない商品は名前と公式URLが要る`);
      const urls = [p.officialUrl, ...(p.sources ?? []).map((s) => s.url), p.priceSource.url].join(" ");
      assert.doesNotMatch(urls, /a8\.net|afl\.rakuten|hb\.afl|amazon|afl\.|valuecommerce|accesstrade|moshimo|afb/i, `${where}: 広告のリンク`);
    }
  }
});

test("読者に見える文に「｜」「ざっくり」「ポイント還元」を書かない", () => {
  for (const slug of SLUGS) {
    const text = strings(guides[slug]).join("\n");
    assert.doesNotMatch(text, /｜/, slug);
    assert.doesNotMatch(text, /ざっくり/, slug);
    assert.doesNotMatch(text, /ポイント還元/, slug);
  }
  // ふるさと納税のページはポイントの話をしない（約束もしない）
  assert.doesNotMatch(strings(guides["furusato-sites"]).join("\n"), /ポイント/);
});

test("保険相談のページは、火災保険の囲みの bang-kasai 以外に PR を入れない", () => {
  const g = guides["hoken-soudan"];
  const sponsored = g.products.filter((p) => p.partner).map((p) => p.partner);
  assert.deepEqual(sponsored, ["bang-kasai"]);
  assert.deepEqual(g.quickPick, []);
  const fire = (g.sideSections ?? []).find((s) => s.id === "fire");
  assert.ok(fire, "火災保険の囲み");
  assert.deepEqual(fire.products, ["bang-kasai"]);
  for (const persona of g.personas) assert.ok(!persona.picks.includes("bang-kasai"), "結論に火災保険を入れない");
});

test("楽天モバイル・証券・NISA・カード・ローン・不動産の広告を入れない", () => {
  const banned = /rakuten-mobile|matsui|dmm-kabu|epos|ohya|loan|nisa/i;
  for (const slug of SLUGS) {
    for (const p of guides[slug].products) assert.doesNotMatch(p.partner ?? "", banned, slug);
  }
});

// ---- 表示（Next.js を起動せず、esbuild でまとめて実際のコンポーネントを描く） ----
let rendered;
async function renderAll() {
  if (rendered) return rendered;
  const { build } = require("esbuild");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "saisoku-life-compare-"));
  const outfile = path.join(dir, "render.cjs");
  const entry = `
    import { createElement } from "react";
    import { renderToStaticMarkup } from "react-dom/server";
    import { COMPARE_PUBLIC, getAllBuyingGuides, getBuyingGuide, isGuideIndexable, isLifeCompareSlug, lifeCompareGuide, LIFE_COMPARE_SLUGS } from "@/lib/buying-guides";
    import { buildGuideView } from "@/components/compare/view";
    import VariantA from "@/components/compare/VariantA";
    import { generateMetadata } from "@/app/compare/[slug]/page";
    export async function run() {
      const out = {};
      for (const slug of LIFE_COMPARE_SLUGS) {
        const guide = getBuyingGuide(slug);
        if (!guide) { out[slug] = null; continue; }
        const view = buildGuideView(guide);
        out[slug] = {
          html: renderToStaticMarkup(createElement(VariantA, { view })),
          jsonLd: view.jsonLd,
          meta: await generateMetadata({ params: Promise.resolve({ slug }) }),
          sponsored: view.products.filter((p) => p.sponsored).map((p) => p.key),
          side: view.sideSections.map((s) => s.products.map((p) => p.key)),
          href: lifeCompareGuide(slug)?.href,
        };
      }
      const thin = {};
      for (const g of getAllBuyingGuides()) {
        if (isGuideIndexable(g)) continue;
        thin[g.slug] = (await generateMetadata({ params: Promise.resolve({ slug: g.slug }) })).robots;
      }
      return { COMPARE_PUBLIC, out, thin, notLife: isLifeCompareSlug("ai-voice-recorder") };
    }
  `;
  await build({
    stdin: { contents: entry, resolveDir: root, loader: "tsx", sourcefile: "life-compare-entry.tsx" },
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    tsconfig: path.join(root, "tsconfig.json"),
    logLevel: "error",
    define: { "process.env.NODE_ENV": '"test"' },
  });
  try {
    rendered = await require(outfile).run();
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  return rendered;
}

test("5本とも表示でき、検索に出す（robots を付けない＝index・follow。2026-11-11 オーナー承認・台帳 W42）", async () => {
  const { COMPARE_PUBLIC, out, thin, notLife } = await renderAll();
  assert.equal(COMPARE_PUBLIC, false, "記事の商品枠からの話題の案内（buyingGuideForTopic）は別の判断");
  assert.equal(notLife, false);
  // 旧形式の薄いページは noindex のまま
  assert.ok(Object.keys(thin).length > 0);
  for (const [slug, robots] of Object.entries(thin)) assert.deepEqual(robots, { index: false, follow: true }, slug);
  for (const slug of SLUGS) {
    assert.ok(out[slug], `${slug} が読み込めない（商品が2つ未満か JSON の誤り）`);
    assert.equal(out[slug].meta.robots, undefined, slug);
    assert.equal(out[slug].meta.alternates.canonical, `/compare/${slug}`);
    const types = out[slug].jsonLd.map((x) => x["@type"]);
    assert.deepEqual(types, ["Article", "ItemList", "BreadcrumbList", "FAQPage"], slug);
    assert.doesNotMatch(JSON.stringify(out[slug].jsonLd), /a8\.net|ArticleSummary/, slug);
    assert.equal(out[slug].href, `/compare/${slug}`);
    assert.match(out[slug].html, /11月1[01]日時点/, `${slug}: 確認日が見えない`);
    assert.doesNotMatch(out[slug].html, /｜|ざっくり/, slug);
  }
});

test("PR のボタンは rel に sponsored を含み、[data-aff-pos] の中にある（AffClickTracker が数える）", async () => {
  const { out } = await renderAll();
  for (const slug of SLUGS) {
    const html = out[slug].html;
    const links = [...html.matchAll(/<a [^>]*>/g)].map((m) => m[0]);
    const sponsored = links.filter((a) => /rel="[^"]*sponsored/.test(a));
    assert.ok(sponsored.length > 0, `${slug}: PR のリンクがない`);
    for (const a of sponsored) {
      assert.match(a, /data-aff-pos="compare"/, `${slug}: ${a}`);
      assert.match(a, /href="https:\/\/r?px\.a8\.net\//, `${slug}: ${a}`);
    }
    // 提携していない商品のリンクは sponsored にしない（nofollow で公式へ）
    for (const a of links.filter((x) => /data-aff-pos/.test(x) && !/sponsored/.test(x))) {
      assert.doesNotMatch(a, /a8\.net/, `${slug}: ${a}`);
      assert.match(a, /rel="nofollow noopener"/, `${slug}: ${a}`);
    }
  }
  // 保険相談：比較の本体に PR はなく、火災保険の囲みだけに出る
  assert.deepEqual(out["hoken-soudan"].sponsored, []);
  assert.deepEqual(out["hoken-soudan"].side, [["bang-kasai"]]);
  const html = out["hoken-soudan"].html;
  const fireAt = html.indexOf('id="a-side-fire"');
  assert.ok(fireAt > 0, "火災保険の囲みがない");
  const firstSponsored = html.search(/rel="sponsored/);
  assert.ok(firstSponsored > fireAt, "火災保険の囲みより前に PR のリンクがある");
});

test("サイトマップは検索に出す比較ページ（新形式）だけを載せる（台帳 W42）", () => {
  const sitemap = read("lib/sitemap.ts");
  assert.match(sitemap, /getIndexableBuyingGuides\(\)\.length > 0/);
  assert.match(sitemap, /\.\.\.getIndexableBuyingGuides\(\)\.map/);
  assert.doesNotMatch(sitemap, /getAllBuyingGuides/);
  assert.match(read("lib/buying-guides.ts"), /export const COMPARE_PUBLIC = false;/);
  assert.match(read("app/compare/[slug]/page.tsx"), /isGuideIndexable\(guide\) \? \{\} : \{ robots: \{ index: false, follow: true \} \}/);
});
