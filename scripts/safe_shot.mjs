#!/usr/bin/env node
/**
 * 本番（や手元）のページを、訪問者の数に入れずに撮る（2026-11-11 台帳 O17）。エージェント・手作業の撮影は必ずこれを使う。
 *   node scripts/safe_shot.mjs https://ai-tech-express.jp/articles/<slug> --out shot.png [--width 390] [--height 844] [--full]
 *        [--selector ".nr-cover"] [--scroll-to ".nr-cover"] [--dark]
 * 効くこと: Cloudflare Web Analytics（static.cloudflareinsights.com・/cdn-cgi/rum）と自前の計測（/api/aff/*）を止める（scripts/browser_guard.cjs）、
 *   同じサイトへの通信に X-Saisoku-Internal: 1、URL に ?_internal=1、広告・提携先の通信も止める。止めた件数を最後に出す。
 * 依存: playwright-core（`npm i --no-save playwright-core`。別の場所に入れたなら PLAYWRIGHT_CORE=/path/to/node_modules/playwright-core）と Chrome。
 */
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import guard from "./browser_guard.cjs";

const require = createRequire(import.meta.url);
const argv = process.argv.slice(2);
const flag = (name) => argv.includes(`--${name}`);
const opt = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : fallback;
};
const url = argv.find((a) => /^https?:\/\//.test(a));
const out = opt("out", "shot.png");
if (!url) {
  console.error("使い方: node scripts/safe_shot.mjs <URL> --out shot.png [--width 390] [--full] [--selector CSS] [--scroll-to CSS] [--dark]");
  process.exit(2);
}

function loadPlaywright() {
  const tries = [process.env.PLAYWRIGHT_CORE, "playwright-core", "playwright"].filter(Boolean);
  for (const name of tries) {
    try {
      return require(name);
    } catch {
      /* 次を試す */
    }
  }
  console.error("playwright-core が見つからない（npm i --no-save playwright-core か PLAYWRIGHT_CORE=...）");
  process.exit(2);
}

/** 広告・提携先（読み込むとインプレッションやクリックの数が水増しされる） */
const AD_HOST = /(^|\.)(a8\.net|rakuten\.co\.jp|amazon\.co\.jp|amzn\.to|amazon-adsystem\.com|googlesyndication\.com|doubleclick\.net|googleadservices\.com|adtrafficquality\.google|google-analytics\.com|googletagmanager\.com|facebook\.net)$/i;

const { chromium } = loadPlaywright();
const chrome = process.env.CHROME_PATH || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"].find((p) => existsSync(p));
const browser = await chromium.launch({ headless: true, ...(chrome ? { executablePath: chrome } : {}), args: [`--host-resolver-rules=${guard.HOST_RESOLVER_RULE}`] });
const width = Number(opt("width", "390"));
const height = Number(opt("height", "844"));
const mobile = width < 768;
const ctx = await browser.newContext({
  viewport: { width, height },
  deviceScaleFactor: mobile ? 3 : 1,
  isMobile: mobile,
  hasTouch: mobile,
  locale: "ja-JP",
  timezoneId: "Asia/Tokyo",
  colorScheme: flag("dark") ? "dark" : "light",
  userAgent: mobile
    ? "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1 saisoku-safe-shot"
    : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 saisoku-safe-shot",
});
const target = new URL(url);
let blocked = 0;
await ctx.route("**/*", (route) => {
  const req = route.request();
  let u;
  try {
    u = new URL(req.url());
  } catch {
    return route.continue();
  }
  if (guard.shouldBlock(u.href) || AD_HOST.test(u.hostname)) {
    blocked += 1;
    return route.abort("blockedbyclient");
  }
  if (u.origin === target.origin) return route.continue({ headers: { ...req.headers(), "x-saisoku-internal": "1" } });
  return route.continue();
});
// 念のため最後に登録（後に登録した route が先に動く）
await guard.guardPlaywright(ctx);
const page = await ctx.newPage();
const rumSeen = [];
// 実際に届いた（止められなかった）計測の通信だけ数える
page.on("requestfinished", (req) => {
  if (guard.isRumBeacon(req.url())) rumSeen.push(req.url());
});
if (!target.searchParams.has("_internal")) target.searchParams.set("_internal", "1");
await page.goto(target.href, { waitUntil: "load", timeout: 60000 });
await page.evaluate(() => document.fonts?.ready);
await page.waitForTimeout(800);
const scrollTo = opt("scroll-to", "");
if (scrollTo) {
  await page.locator(scrollTo).first().scrollIntoViewIfNeeded();
  // 遅れて読む写真（loading="lazy"）が出るまで待つ
  await page.waitForTimeout(1500);
}
const selector = opt("selector", "");
if (selector) await page.locator(selector).first().screenshot({ path: out });
else await page.screenshot({ path: out, fullPage: flag("full") });
await browser.close();
console.log(`saved ${out}（止めた通信 ${blocked} 件・Cloudflare の計測に届いた通信 ${rumSeen.length === 0 ? "なし" : rumSeen.length}）`);
