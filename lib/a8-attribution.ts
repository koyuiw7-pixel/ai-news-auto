import { BOT_UA, GUIDE_PATH } from "./revenue-funnel";

/** A8へ送るのは記事・掲載位置の固定分類だけ。個人・検索語・参照URLは送らない。 */
export const A8_ENTRY_QUERY = "sa_from";
export const A8_ARTICLE_CODES = {
  "/guides/dify-free-api-cost": "difyfree",
  "/guides/dify-1-18-startup-check": "difystartup",
} as const;
export const A8_ENTRY_CODES = ["difyfree", "difystartup", "direct", "internal", "unknown"] as const;
export type A8Entry = typeof A8_ENTRY_CODES[number];
export type A8Position = "table" | "cards";

/** Next Linkのpropsに渡す。DOMだけの書換えではクライアント遷移に反映されないため。 */
export function difyDecisionHref(articlePath: string, href: string): string {
  const code = Object.hasOwn(A8_ARTICLE_CODES, articlePath) ? A8_ARTICLE_CODES[articlePath as keyof typeof A8_ARTICLE_CODES] : undefined;
  return code && href === GUIDE_PATH ? `${href}?${A8_ENTRY_QUERY}=${code}` : href;
}

export function a8EntryOf(search: string, referrer: string, origin: string): A8Entry {
  const params = new URLSearchParams(search).getAll(A8_ENTRY_QUERY);
  if (params.length) {
    // 自由入力・重複・空値を記事名へ昇格させない。共有されたURLも分類であり訪問者IDではない。
    return params.length === 1 && Object.values(A8_ARTICLE_CODES).includes(params[0] as "difyfree" | "difystartup")
      ? params[0] as A8Entry : "unknown";
  }
  if (!referrer) return "direct";
  try {
    const ref = new URL(referrer);
    if (ref.origin !== origin) return "direct";
    // SPAではdocument.referrerが最初の読み込みから変わらない。過去の記事名で帰属しない。
    return "internal";
  } catch { return "unknown"; }
}

type PrivacySignals = { webdriver?: boolean; userAgent?: string; doNotTrack?: string | null; globalPrivacyControl?: boolean };
export function a8AttributionAllowed(nav: PrivacySignals): boolean {
  return !nav.webdriver && !BOT_UA.test(nav.userAgent ?? "") && nav.doNotTrack !== "1" && !nav.globalPrivacyControl;
}

/**
 * Dify比較のXServer VPS素材専用。公式id1〜id3だけを追記する。
 * 元URLは再シリアライズせず、a8mat・エンコード・遷移先・fragmentをバイト単位で保持。
 * 既存のidや未確認形式を上書きしない。Amazon/楽天や他の広告への共通適用は禁止。
 */
export function appendDifyA8Attribution(href: string, entry: A8Entry, position: A8Position): string {
  if (!A8_ENTRY_CODES.includes(entry) || !["table", "cards"].includes(position) || /[^\x21-\x7e]/.test(href) || !href.startsWith("https://px.a8.net/svt/ejp?")) return href;
  try {
    const url = new URL(href);
    if (url.protocol !== "https:" || url.hostname !== "px.a8.net" || url.port || url.username || url.password || url.pathname !== "/svt/ejp") return href;
    const keys = [...url.searchParams.keys()];
    if (keys.some((key) => /^id[1-5]$/i.test(key)) || keys.some((key) => !["a8mat", "a8ejpredirect"].includes(key))) return href;
    if (url.searchParams.getAll("a8mat").length !== 1 || !url.searchParams.get("a8mat")?.trim()) return href;
    if (url.searchParams.getAll("a8ejpredirect").length > 1) return href;
    const hashAt = href.indexOf("#");
    const base = hashAt < 0 ? href : href.slice(0, hashAt);
    const hash = hashAt < 0 ? "" : href.slice(hashAt);
    return `${base}${base.endsWith("&") ? "" : "&"}id1=${entry}&id2=difyhost&id3=${position}${hash}`;
  } catch { return href; }
}

/** 広告通信を行わずリンクの固定分類だけを準備。解除時は自分が書いた値だけを戻す。 */
export function installDifyA8Attribution(pathname: string, search: string, doc: Document, nav: PrivacySignals, origin: string): () => void {
  if (pathname !== GUIDE_PATH || !a8AttributionAllowed(nav)) return () => {};
  const entry = a8EntryOf(search, doc.referrer, origin);
  const changed: { link: Element; original: string; appended: string }[] = [];
  for (const link of doc.querySelectorAll('a[data-a8-dify="v1"][data-funnel-choice="xserver-dify"][rel~="sponsored"]')) {
    const pos = link.closest("[data-aff-pos]")?.getAttribute("data-aff-pos");
    if (pos !== "choose-table" && pos !== "choose-cards") continue;
    const original = link.getAttribute("href");
    if (!original) continue;
    const appended = appendDifyA8Attribution(original, entry, pos === "choose-table" ? "table" : "cards");
    if (appended === original) continue;
    try {
      link.setAttribute("href", appended);
      changed.push({ link, original, appended });
    } catch { /* 計測の失敗で元のリンク操作を止めない。 */ }
  }
  return () => {
    for (const { link, original, appended } of changed) {
      if (link.getAttribute("href") === appended) link.setAttribute("href", original);
    }
  };
}
