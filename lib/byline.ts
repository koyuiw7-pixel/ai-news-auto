/**
 * 記事の題名のすぐ下の署名の行（2026-11-10 Google Discover・Google ニュースの準備）。
 * Google は「誰が書いたか（署名）と、いつ公開・更新したか（日付と時刻）」をはっきり見せるよう案内している。
 * 公開は構造化データの datePublished（generatedAt。無ければ publishedAt）と同じ時刻、
 * 更新は updatedAt（dateModified と同じ）が公開と分単位で違うときだけ出す。依存の無い小さなファイル（テストからも読む）
 */
const FORMAT = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "Asia/Tokyo",
});

/** 「2026/11/10 02:18」（日本時間）。読めない値は空 */
export function bylineTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : FORMAT.format(date);
}

export type BylineDates = { published: string; publishedLabel: string; updated: string | null; updatedLabel: string | null };

export function bylineDates(article: { generatedAt?: string | null; publishedAt?: string | null; updatedAt?: string | null }): BylineDates | null {
  const published = article.generatedAt || article.publishedAt || "";
  const publishedLabel = bylineTime(published);
  if (!publishedLabel) return null;
  const updatedLabel = bylineTime(article.updatedAt);
  const later = Boolean(article.updatedAt) && Date.parse(article.updatedAt as string) > Date.parse(published);
  const updated = updatedLabel && updatedLabel !== publishedLabel && later ? (article.updatedAt as string) : null;
  return { published, publishedLabel, updated, updatedLabel: updated ? updatedLabel : null };
}
