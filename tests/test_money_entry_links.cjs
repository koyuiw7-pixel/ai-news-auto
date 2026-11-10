const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

// お金のページへの入口（2026-11-10 M6）。記事の PR の囲みの下の「料金と条件を比べる」、足元のお金のリンク、トップの入口、/choose の一覧。
// Next.js を起動せず、esbuild でまとめて実際のコンポーネントを描いて確かめる。
const root = path.resolve(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const SLUGS = ["kakuyasu-sim", "hikari", "denki-gas", "hoken-soudan", "furusato-sites"];

let rendered;
async function renderAll() {
  if (rendered) return rendered;
  const { build } = require("esbuild");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "saisoku-money-entry-"));
  const outfile = path.join(dir, "render.cjs");
  const entry = `
    import fs from "node:fs";
    import { createElement } from "react";
    import { renderToStaticMarkup } from "react-dom/server";
    import Footer from "@/components/Footer";
    import ActionAd from "@/components/ActionAd";
    import HomePage from "@/app/page";
    import ChooseIndexPage, { metadata as chooseMeta } from "@/app/choose/page";
    import { getAllChooseGuides } from "@/lib/choose";
    import { actionAdForArticle, compareLinkForRule, COMPARE_FOR_RULE } from "@/lib/action-ad";
    export async function run() {
      const article = (slug) => JSON.parse(fs.readFileSync("content/articles/" + slug + ".json", "utf8"));
      const heater = actionAdForArticle(article("heater-power-cost-per-hour"));
      const plain = heater && { ...heater, compare: undefined };
      const rules = Object.fromEntries(Object.keys(COMPARE_FOR_RULE).map((k) => [k, compareLinkForRule(k)?.href]));
      return {
        footer: renderToStaticMarkup(createElement(Footer)),
        heater,
        heaterHtml: heater ? renderToStaticMarkup(createElement(ActionAd, { ad: heater })) : "",
        heaterPlainHtml: plain ? renderToStaticMarkup(createElement(ActionAd, { ad: plain })) : "",
        rules,
        unknownRule: compareLinkForRule("leak"),
        home: renderToStaticMarkup(createElement(HomePage)),
        choose: renderToStaticMarkup(createElement(ChooseIndexPage)),
        chooseMeta,
        chooseSlugs: getAllChooseGuides().map((g) => g.slug),
      };
    }
  `;
  await build({
    stdin: { contents: entry, resolveDir: root, loader: "tsx", sourcefile: "money-entry.tsx" },
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    tsconfig: path.join(root, "tsconfig.json"),
    logLevel: "error",
    loader: { ".css": "empty" },
    define: { "process.env.NODE_ENV": '"test"' },
  });
  const cwd = process.cwd();
  process.chdir(root);
  try {
    rendered = await require(outfile).run();
  } finally {
    process.chdir(cwd);
    fs.rmSync(dir, { recursive: true, force: true });
  }
  return rendered;
}

const hrefs = (html) => [...html.matchAll(/href="([^"]+)"/g)].map((m) => m[1]);
const footerOf = (html) => html.slice(html.indexOf("<footer"), html.indexOf("</footer>"));

test("足元: お金のページ（計算・比較5本・手続き2本）があり、AI の選び方ガイドは /choose の一覧から", async () => {
  const { footer } = await renderAll();
  const links = hrefs(footer);
  for (const href of ["/tools/furusato-limit", "/tools/defense-tax", ...SLUGS.map((s) => `/compare/${s}`), "/guides/jidou-teate", "/guides/kogaku-ryoyohi", "/choose"]) {
    assert.ok(links.includes(href), `足元に ${href} が無い`);
  }
  for (const href of ["/choose/dify-hosting", "/choose/internet-for-ai", "/choose/ai-career"]) {
    assert.ok(!links.some((h) => h.startsWith(href)), `足元に ${href} が残っている`);
  }
  // 足元のお金のリンクは広告ではない
  assert.doesNotMatch(footer, /rel="[^"]*sponsored/);
});

test("記事の PR の囲み（heater-power-cost-per-hour）の下に、電気・ガスの比較への1行。囲みの中身と順は変えない", async () => {
  const { heater, heaterHtml, heaterPlainHtml } = await renderAll();
  assert.ok(heater, "暖房の電気代の記事に PR の囲みが出ない");
  assert.equal(heater.key, "energy");
  assert.equal(heater.compare?.href, "/compare/denki-gas");
  assert.ok(heaterHtml.includes('href="/compare/denki-gas"'));
  assert.ok(heaterHtml.includes("料金と条件を比べる：電気・ガスの契約先の比較"));
  // 広告の囲みの部品に矢印の印は付けない（2026-11-09 オーナー。tests/test_action_ads.py）
  assert.doesNotMatch(heaterHtml, /[→›]/);
  // 1行は囲み（data-aff-pos）の外。囲みの部分は1行が無いときと同じ
  const aside = heaterHtml.slice(0, heaterHtml.indexOf("</aside>") + 8);
  assert.equal(aside, heaterPlainHtml);
  assert.ok(!aside.includes("/compare/denki-gas"));
  const line = heaterHtml.slice(aside.length);
  assert.match(line, /data-money-link=""/);
  assert.doesNotMatch(line, /sponsored|data-aff/);
  assert.equal((heaterHtml.match(/data-aff-pos=/g) ?? []).length, 1);
});

test("話題 → 比較ページの対応（電気・家計 → 電気・ガス、スマホ → 格安SIM、引っ越し → 光回線、ふるさと納税・年末調整 → ふるさと納税サイト）", async () => {
  const { rules, unknownRule } = await renderAll();
  assert.deepEqual(rules, {
    energy: "/compare/denki-gas",
    household: "/compare/denki-gas",
    mobile: "/compare/kakuyasu-sim",
    moving: "/compare/hikari",
    furusato: "/compare/furusato-sites",
    nencho: "/compare/furusato-sites",
  });
  assert.equal(unknownRule, undefined);
});

test("トップ: home-top と home-mid の PR の枠は今までの順。/choose/dify-hosting へのリンクは無く、お金の入口がある", async () => {
  const { home } = await renderAll();
  const top = home.indexOf('data-aff-pos="home-top"');
  const mid = home.indexOf('data-aff-pos="home-mid"');
  assert.ok(top > 0 && mid > top, `${top} ${mid}`);
  const body = home.includes("<footer") ? home.slice(0, home.indexOf("<footer")) : home;
  const links = hrefs(body);
  assert.ok(!links.some((h) => h.startsWith("/choose/dify-hosting")), "トップに /choose/dify-hosting が残っている");
  assert.ok(!links.some((h) => h.startsWith("/choose/internet-for-ai")), "トップに /choose/internet-for-ai が残っている");
  assert.ok(links.includes("/compare/hikari"));
  // 10〜12月はふるさと納税の上限額の計算とサイトの比較（それ以外の月は電気・ガスの比較が先）
  const month = new Date(Date.now() + 9 * 3600 * 1000).getUTCMonth() + 1;
  if (month >= 10) {
    assert.ok(links.includes("/tools/furusato-limit"));
    assert.ok(links.includes("/compare/furusato-sites"));
  } else {
    assert.ok(links.includes("/compare/denki-gas"));
  }
  // 入口は PR の枠の間（上の枠より下、下の枠より上）
  const entry = home.indexOf('data-funnel-pos="home-guides"');
  assert.ok(top < entry && entry < mid);
  // トップの PR の枠の数は今までどおり2つ
  assert.equal((body.match(/data-aff-pos="home-(top|mid)"/g) ?? []).length, 2);
});

test("/choose: 一覧が表示され、/choose/* のすべてと比較ページ5本へリンクする。robots は /choose/* と同じ（指定なし）", async () => {
  const { choose, chooseMeta, chooseSlugs } = await renderAll();
  const links = hrefs(choose);
  assert.ok(chooseSlugs.length >= 3);
  for (const slug of chooseSlugs) assert.ok(links.includes(`/choose/${slug}`), slug);
  for (const slug of SLUGS) assert.ok(links.includes(`/compare/${slug}`), slug);
  assert.equal(chooseMeta.robots, undefined);
  assert.equal(chooseMeta.alternates.canonical, "/choose");
  assert.doesNotMatch(choose, /sponsored|data-aff-pos/);
  assert.doesNotMatch(read("app/choose/[slug]/page.tsx"), /robots/);
});

test("足した文に「｜」と「ざっくり」が無い", async () => {
  const { footer, heaterHtml, choose, home } = await renderAll();
  for (const html of [footerOf(footer), heaterHtml, choose, home]) assert.doesNotMatch(html, /｜|ざっくり/);
  for (const rel of ["app/choose/page.tsx", "components/ActionAd.tsx", "lib/action-ad.ts", "components/Footer.tsx", "app/page.tsx"]) {
    assert.doesNotMatch(read(rel), /｜|ざっくり/, rel);
  }
});
