/**
 * 自動のブラウザ（Playwright・Chrome の CDP・ヘッドレスの撮影）で本番のページを開くときに、訪問者の数え方を汚さないための共通の部品。
 * 2026-11-11 オーナー承認（台帳 O17）: 自分たちの撮影・確かめで、その日の訪問者の数（Cloudflare Web Analytics）が増えていた。
 *
 * 止めるもの:
 *   - Cloudflare Web Analytics（RUM）: エッジで差し込まれる static.cloudflareinsights.com/beacon.min.js と、送り先の /cdn-cgi/rum
 *   - 確かめるだけのとき（verifyOnly。既定）: サイトの自前の計測 /api/aff/*（クリック・表示・読んだ深さ・流入・お金の導線）
 * 使い方（Node・Playwright）:
 *   const { guardPlaywright } = require("./browser_guard.cjs");   // ESM なら import guard from "./browser_guard.cjs"
 *   await guardPlaywright(context);            // ほかの route を登録した「後」に呼ぶ（後に登録した route が先に動く）
 * 自前の route("**\/*") の中で判定するなら shouldBlock(url)。CDP なら Network.setBlockedURLs に CDP_BLOCKED_URLS、
 * Chrome の起動の引数に HOST_RESOLVER_RULE。Python は scripts/browser_guard.py（同じ決まり）。
 * 本番を開く撮影は scripts/safe_shot.mjs を使えば、この部品が必ず効く。
 */

/** Cloudflare Web Analytics（RUM）の読み込みと送信 */
const RUM_HOSTS = ["static.cloudflareinsights.com", "cloudflareinsights.com"];
const RUM_PATH = /^\/cdn-cgi\/rum(?:[/?]|$)/;
/** サイトの自前の計測の受け口（cloudflare/aff.ts・inflow.ts・reading.ts・revenue funnel） */
const OWN_BEACON_PATH = /^\/api\/aff\//;

/** Playwright の route に渡す形（** はどの文字列にも当たる） */
const RUM_GLOBS = ["**/static.cloudflareinsights.com/**", "**/cloudflareinsights.com/**", "**/cdn-cgi/rum**"];
const OWN_BEACON_GLOBS = ["**/api/aff/**"];

/** Chrome DevTools Protocol の Network.setBlockedURLs に渡す形（* はどの文字列にも当たる） */
const CDP_BLOCKED_URLS = ["*://static.cloudflareinsights.com/*", "*://*.cloudflareinsights.com/*", "*/cdn-cgi/rum*", "*/api/aff/*"];

/** Chrome の起動の引数（--host-resolver-rules）に足す決まり。RUM の読み込み元を名前の段階で引けなくする */
const HOST_RESOLVER_RULE = RUM_HOSTS.map((h) => `MAP ${h} ~NOTFOUND`).join(", ");

function parse(url) {
  try {
    return new URL(url);
  } catch {
    return null;
  }
}

/** Cloudflare Web Analytics の読み込み・送信か */
function isRumBeacon(url) {
  const u = parse(url);
  if (!u) return false;
  const host = u.hostname.toLowerCase();
  return RUM_HOSTS.some((h) => host === h || host.endsWith(`.${h}`)) || RUM_PATH.test(u.pathname);
}

/** サイトの自前の計測（/api/aff/*）か */
function isOwnBeacon(url) {
  const u = parse(url);
  return Boolean(u && OWN_BEACON_PATH.test(u.pathname));
}

/** 止めるか。verifyOnly（既定 true）なら自前の計測も止める */
function shouldBlock(url, { verifyOnly = true } = {}) {
  return isRumBeacon(url) || (verifyOnly && isOwnBeacon(url));
}

/**
 * Playwright の BrowserContext か Page に、計測を止める route を足す。
 * ほかの route を登録した後に呼ぶ（Playwright は後に登録した route から順に動かす。先の route が continue() すると後ろには回らない）
 */
async function guardPlaywright(target, { verifyOnly = true } = {}) {
  const globs = [...RUM_GLOBS, ...(verifyOnly ? OWN_BEACON_GLOBS : [])];
  for (const glob of globs) await target.route(glob, (route) => route.abort("blockedbyclient"));
  return target;
}

module.exports = {
  RUM_HOSTS,
  RUM_GLOBS,
  OWN_BEACON_GLOBS,
  CDP_BLOCKED_URLS,
  HOST_RESOLVER_RULE,
  isRumBeacon,
  isOwnBeacon,
  shouldBlock,
  guardPlaywright,
};
