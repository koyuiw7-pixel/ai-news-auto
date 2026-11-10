/**
 * 画面に出す「発表」の時刻。web 記事で元の発表の時刻（sourcePublishedAt）が分からないものは空（「発表」は出さず「掲載」だけ。
 * web 記事の publishedAt は見つけた時刻の代用のことがある）。動画の記事は publishedAt が動画の公開日時なのでそれを使う。
 * 掲載（generatedAt）より後の時刻は、発信元の時間帯の書き違い（「JST」を UTC と読んだ等）なので掲載の時刻で止める（SEO A5）
 */
export function announcedAt(article: {
  sourcePublishedAt?: string;
  generatedAt?: string;
  publishedAt?: string;
  sourceType?: string;
}): string {
  const source = article.sourcePublishedAt || (article.sourceType === "web" ? "" : article.publishedAt || "");
  const sourceTime = Date.parse(source);
  if (!Number.isFinite(sourceTime)) return "";
  const generatedTime = Date.parse(article.generatedAt ?? "");
  return Number.isFinite(generatedTime) && generatedTime < sourceTime ? (article.generatedAt as string) : source;
}
