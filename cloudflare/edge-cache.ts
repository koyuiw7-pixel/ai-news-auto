/**
 * エッジのキャッシュ（cloudflare/worker.ts）の決まりだけを集めたもの。Workers の外（node のテスト）でも読めるよう、
 * ビルド時に作られるファイルや Cache API には触らない（tests/test_worker_cache.cjs）。
 */

/**
 * 新しい記事が出たら、すぐ中身が変わるべきページ（トップ・一覧・サイトマップ・フィード）。
 * ここは前のデプロイで描いた古い版をエッジから返さず、その場で描き直す（描き直しは 0.2〜1.5 秒）。
 * 古い版を返すと、検索のロボットやフィードの読み手が、新しい記事の無い一覧を受け取ってしまう（seo A1。2026-11-10）
 */
export function mustBeCurrent(pathname: string): boolean {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return (
    path === "/" ||
    path === "/news" ||
    path === "/articles" ||
    path === "/sitemap.xml" ||
    path === "/news-sitemap.xml" ||
    path === "/feed.xml" ||
    /^\/sitemaps\/[^/]+\.xml$/.test(path) ||
    /^\/feeds\/[^/]+\.xml$/.test(path)
  );
}

/**
 * 表示に関係しない計測用のパラメータ（シェアボタンの utm_*・SNS や広告のクリック ID・紹介元の印）。
 * キャッシュのキーから外し、同じページを別物として描き直さない。
 * 外してよいものだけを並べる（?v=・?_cold=・?_internal=・?slug=・?design= など、ページを変えるものは残す）
 */
const TRACKING_PARAMS = new Set([
  "fbclid",
  "gclid",
  "igshid",
  "ref",
  "s",
  "t",
  "msclkid",
  "yclid",
  "twclid",
  "ttclid",
  "_gl",
  "srsltid",
  "mc_cid",
]);

/** メールの登録・解除のページは ?s=（結果）・?t=（解除の合言葉）を画面で読むので、キーから外さない */
const KEEPS_S_AND_T = /^\/newsletter(?:\/|$)/;

export function isTrackingParam(name: string, pathname: string): boolean {
  if (/^utm_/.test(name)) return true;
  if (name === "q" && pathname === "/search") return true; // 検索はブラウザ側で行うので、ページは同じ
  if ((name === "s" || name === "t") && KEEPS_S_AND_T.test(pathname)) return false;
  return TRACKING_PARAMS.has(name);
}

/** キャッシュのキーにする URL（計測用のパラメータを外し、JS・CSS の組のハッシュ __c を付ける） */
export function edgeCacheKeyUrl(url: URL, codeHash: string): string {
  const key = new URL(url);
  for (const name of [...key.searchParams.keys()]) {
    if (isTrackingParam(name, key.pathname)) key.searchParams.delete(name);
  }
  key.searchParams.set("__c", codeHash);
  return key.toString();
}

/**
 * エッジに見つかった写しをどう使うか。
 *  - "fresh" … 今の版で描いたもの（か、版に関係しない画像）。そのまま返す
 *  - "stale" … 前の版で描いたもの。すぐ返し、裏で今の版に作り直す（記事ページなど。今までどおり）
 *  - "render" … 前の版で描いたトップ・一覧・サイトマップ・フィード。返さずに、その場で描き直す
 */
export type EdgeHitDecision = "fresh" | "stale" | "render";

export function edgeHitDecision(pathname: string, cachedVersion: string | null, currentVersion: string, immutable = false): EdgeHitDecision {
  if (immutable || cachedVersion === currentVersion) return "fresh";
  return mustBeCurrent(pathname) ? "render" : "stale";
}

/**
 * 自社の確かめ（ヘッダー X-Saisoku-Internal: 1 か ?_internal=1）か。このときだけ Worker の内訳（Server-Timing）を返す（台帳 W43）。
 * 読者・検索のロボットには内訳を見せず、エッジのキャッシュにも残さない（cloudflare/worker.ts の forEdge）
 */
export function isInternalRequest(headers: { get(name: string): string | null }, url: URL): boolean {
  return headers.get("x-saisoku-internal") === "1" || url.searchParams.get("_internal") === "1";
}
