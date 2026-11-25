const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

// トップの最初の画面は「自分のお金と暮らしの数字」の入口から（2026-11-25 AdSense の3回目の申請の前の点検）。
// Next.js を起動せず、esbuild でトップを描いて確かめる（tests/test_money_entry_links.cjs と同じやり方）。
const root = path.resolve(__dirname, "..");
const EXPECTED = [
  "/articles/december-2026-money-calendar",
  "/articles/price-changes-november-february",
  "/articles/data-leaks-recalls-checklist",
  "/articles/japan-benefits-allowances-guide",
  "/tools/child-allowance",
];

let rendered;
async function renderHome() {
  if (rendered) return rendered;
  const { build } = require("esbuild");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "saisoku-home-money-"));
  const outfile = path.join(dir, "render.cjs");
  const entry = `
    import { createElement } from "react";
    import { renderToStaticMarkup } from "react-dom/server";
    import HomePage from "@/app/page";
    import { HOME_MONEY_ENTRY } from "@/components/HomeMoneyEntry";
    import { heroShowsPhoto } from "@/lib/home-lead";
    export async function run() {
      return { home: renderToStaticMarkup(createElement(HomePage)), entry: HOME_MONEY_ENTRY, heroShowsPhoto };
    }
  `;
  await build({
    stdin: { contents: entry, resolveDir: root, loader: "tsx", sourcefile: "home-money.tsx" },
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

test("入口の5本は決めた順で、行き先は実在するページだけ", async () => {
  const { entry } = await renderHome();
  assert.deepEqual(entry.map((e) => e.href), EXPECTED);
  for (const { href, label } of entry) {
    assert.ok(label && !/[｜|]/.test(label) && !label.includes("ざっくり"), label);
    const m = /^\/articles\/(.+)$/.exec(href);
    if (m) assert.ok(fs.existsSync(path.join(root, "content/articles", `${m[1]}.json`)), `${href} の記事が無い`);
    else assert.ok(fs.existsSync(path.join(root, "app", href.slice(1), "page.tsx")), `${href} のページが無い`);
  }
});

test("トップでは入口が主役の記事・見出し・AI の新着より上にある", async () => {
  const { home } = await renderHome();
  const at = (needle) => home.indexOf(needle);
  const entry = at('data-home-zone="money-entry"');
  assert.ok(entry >= 0, "入口が無い");
  assert.ok(home.includes("自分のお金と暮らしの数字"));
  for (const later of ['aria-label="注目の記事"', 'data-home-zone="headlines"', 'id="latest-heading"']) {
    const pos = at(later);
    if (pos >= 0) assert.ok(entry < pos, `${later} より上に入口が無い`);
  }
  // 入口の中のリンクは5本とも描かれている
  const block = home.slice(entry, home.indexOf("</section>", entry));
  for (const href of EXPECTED) assert.ok(block.includes(`href="${href}"`), `${href} が入口に無い`);
});

test("主役の写真: AI のイメージ・写真なしは出さない（別の素材写真に替えない）。公式の写真は出す", async () => {
  const { heroShowsPhoto } = await renderHome();
  assert.equal(heroShowsPhoto({ photo: { src: "https://ai-tech-express.jp/img/x.jpg", ai: true } }), false);
  assert.equal(heroShowsPhoto({ photo: undefined }), false);
  assert.equal(heroShowsPhoto({ photo: { src: "https://ai-tech-express.jp/img/x.jpg" } }), true);
});
