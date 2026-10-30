/** 集計する導線を限定。参照元URL・検索語・自由入力をサーバーへ送らない。 */
export const FUNNEL = "dify-hosting";
export const GUIDE_PATH = "/choose/dify-hosting";
export const SOURCES = ["google", "bing", "x", "threads", "facebook", "hatena", "direct", "internal", "other"] as const;
export type Source = typeof SOURCES[number];
export const STAGES = ["entry_view", "guide_click", "guide_view", "comparison_view", "choice_click"] as const;
export type Stage = typeof STAGES[number];
export const CHOICES = ["dify-cloud", "local-pc", "xserver-dify"] as const;
// Search Consoleの検査はGooglebotを名乗らないため、検査用UAも明示して除外する。
export const BOT_UA = /bot|crawl|spider|slurp|headless|lighthouse|pagespeed|preview|phantom|puppeteer|playwright|selenium|python|curl|wget|google-inspectiontool|googleother/i;

export function sourceOf(search: string, referrer: string, origin: string): Source {
  const utm = new URLSearchParams(search).get("utm_source")?.toLowerCase();
  const aliases: Record<string, Source> = { twitter: "x", "t.co": "x", fb: "facebook", hatenabookmark: "hatena" };
  if (utm) return aliases[utm] ?? (SOURCES.includes(utm as Source) ? utm as Source : "other");
  if (!referrer) return "direct";
  try {
    const ref = new URL(referrer);
    if (ref.origin === origin) return "internal";
    const host = ref.hostname.toLowerCase();
    if (/^(www\.)?google\.(com|co\.jp)$/.test(host)) return "google";
    if (/(^|\.)bing\.com$/.test(host)) return "bing";
    if (/^(t\.co|x\.com|twitter\.com)$/.test(host)) return "x";
    if (/(^|\.)threads\.(net|com)$/.test(host)) return "threads";
    if (/(^|\.)facebook\.com$/.test(host)) return "facebook";
    if (/(^|\.)hatena\.ne\.jp$/.test(host)) return "hatena";
  } catch { /* malformed referrers are only an unknown bucket */ }
  return "other";
}

export function validFunnelEvent(stage: string, path: string, choice: string): boolean {
  if (stage === "entry_view") return path === "/guides" && choice === "";
  if (stage === "guide_click") return /^\/[A-Za-z0-9/._~-]{0,200}$/.test(path) && path !== GUIDE_PATH && choice === "";
  if (stage === "guide_view" || stage === "comparison_view") return path === GUIDE_PATH && choice === "";
  return stage === "choice_click" && path === GUIDE_PATH && CHOICES.includes(choice as typeof CHOICES[number]);
}
