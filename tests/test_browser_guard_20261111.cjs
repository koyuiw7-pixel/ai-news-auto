// 2026-11-11 オーナー承認（台帳 O17）: 自動・エージェントのブラウザで本番を開くときは、訪問者の計測（Cloudflare Web Analytics）と自前の計測を止める。
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const guard = require("../scripts/browser_guard.cjs");

test("止めるのは Cloudflare Web Analytics と /api/aff/*（確かめるだけのとき）だけ", () => {
  assert.equal(guard.shouldBlock("https://static.cloudflareinsights.com/beacon.min.js/v8"), true);
  assert.equal(guard.shouldBlock("https://ai-tech-express.jp/cdn-cgi/rum"), true);
  assert.equal(guard.shouldBlock("https://ai-tech-express.jp/cdn-cgi/rum?t=1"), true);
  assert.equal(guard.shouldBlock("https://ai-tech-express.jp/api/aff/read"), true);
  assert.equal(guard.shouldBlock("https://ai-tech-express.jp/api/aff/click", { verifyOnly: false }), false);
  assert.equal(guard.shouldBlock("https://static.cloudflareinsights.com/beacon.min.js", { verifyOnly: false }), true);
  // ページそのもの・画像の変換（/cdn-cgi/image）は止めない
  assert.equal(guard.shouldBlock("https://ai-tech-express.jp/articles/x"), false);
  assert.equal(guard.shouldBlock("https://ai-tech-express.jp/cdn-cgi/image/width=640/x.jpg"), false);
  assert.ok(guard.CDP_BLOCKED_URLS.includes("*/cdn-cgi/rum*"));
  assert.match(guard.HOST_RESOLVER_RULE, /MAP static\.cloudflareinsights\.com ~NOTFOUND/);
});

test("guardPlaywright は計測の route を止める（abort）", async () => {
  const routes = [];
  await guard.guardPlaywright({ route: async (glob, fn) => routes.push([glob, fn]) });
  assert.deepEqual(routes.map(([g]) => g), [...guard.RUM_GLOBS, ...guard.OWN_BEACON_GLOBS]);
  let aborted = 0;
  await routes[0][1]({ abort: () => { aborted += 1; } });
  assert.equal(aborted, 1);
});

test("Python 版も同じ決まり", () => {
  const py = read("scripts/browser_guard.py");
  for (const g of [...guard.RUM_GLOBS, ...guard.OWN_BEACON_GLOBS]) assert.ok(py.includes(`"${g}"`), g);
});

/** リポジトリの中で、ブラウザを動かしてページを開くファイル（本番を開く可能性がある） */
function browserScripts() {
  const out = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(path.join(root, dir))) {
      const rel = path.join(dir, name);
      const full = path.join(root, rel);
      if (fs.statSync(full).isDirectory()) {
        if (!["node_modules", "__pycache__"].includes(name)) walk(rel);
        continue;
      }
      if (!/\.(mjs|cjs|js|ts|py)$/.test(name) || /browser_guard|test_browser_guard/.test(name)) continue;
      const text = fs.readFileSync(full, "utf8");
      if (/\b(page|p)\.goto\(|Page\.navigate|chromium\.launch|webkit\.launch|firefox\.launch/.test(text)) out.push([rel, text]);
    }
  };
  for (const dir of ["scripts", "tests", "ops"]) if (fs.existsSync(path.join(root, dir))) walk(dir);
  return out;
}

test("ブラウザでページを開くスクリプトは、どれも browser_guard を使う（新しく足すときも）", () => {
  const files = browserScripts();
  assert.ok(files.length >= 5, files.map(([f]) => f).join(", "));
  for (const [file, text] of files) {
    // shorts_v3.py は shorts_v2 の判定に加え、自分の route でも beacon_blocked を使う
    assert.match(text, /browser_guard|beacon_blocked/, `${file}: scripts/browser_guard（.cjs / .py）で計測を止めていない`);
  }
});

test("画面側の自前の計測4つは、自動ブラウザ（navigator.webdriver）では送らない", () => {
  for (const file of ["components/ReadingBeacon.tsx", "components/InflowBeacon.tsx", "components/AffClickTracker.tsx", "components/RevenueFunnelTracker.tsx"]) {
    assert.match(read(file), /navigator\.webdriver/, file);
  }
});

test("エージェント向けの説明と台帳に決まりがある", () => {
  assert.match(read("AGENTS.md"), /cloudflareinsights[\s\S]{0,200}cdn-cgi\/rum/);
  assert.match(read("docs/automation.md"), /static\.cloudflareinsights\.com[\s\S]{0,200}\/cdn-cgi\/rum/);
  assert.match(read("docs/owner_rules.md"), /^\| O17 \|/m);
});
