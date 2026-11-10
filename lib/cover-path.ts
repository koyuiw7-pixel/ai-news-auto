/** 独自カバー画像の URL（クライアントの部品からも読めるよう、依存のない小さなファイルに置く） */

/**
 * カバー画像の版。デザイン（ラベルの文言など）を変えたら1つ上げる。
 * /cover/<slug> はブラウザ・CDN で7日（immutable）使い回されるので、URL に ?v= を付けて新しい画像を取りに行かせる。
 * 2: 「速報」は速報の記事だけ、ほかは「ニュース」（2026-11-03 の画面の点検 B）
 * 3: 画像の題名を検索向けの seoTitle から記事の題名（lib/headline.ts の articleTitle）に替えた（2026-11-03 の点検 10）
 * 4: 記事の写真が無いとき、表紙用の AI のイメージ（coverImage）を「画像はイメージ（AI生成）」つきで敷く（2026-11-07 不二家の記事で暗い画像が出た）
 * 5: 図の表紙（imageCredit kind figure・imageKind cover）は図をそのまま使い、見出し・ラベル・注記を重ねない（2026-11-10 同じ題名が2回出ていた）
 * 6: 「ニュース」の札を折り返さない・発表元は団体名を1行で（2026-11-11 読者目線レビュー 13位）
 */
export const COVER_VERSION = 6;

/** 題名の短いハッシュ（題名を直したら URL が変わり、ブラウザ・SNS・エッジに残った古い画像を使わせない） */
export function titleHash(title: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < title.length; i++) {
    h ^= title.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(36);
}

/**
 * 独自カバー画像（/cover/[slug]）のパス（版＋題名のハッシュつき）。全記事で作る。
 */
export function coverPath(article: { slug: string; title?: string | null; thumbnail?: string | null; coverImage?: string | null }): string {
  const title = (article.title ?? "").trim();
  // 画像を差し替えたときも URL を変える（2026-11-07 オーナー指摘：画像を直したのに SNS のカードが古い画像のままだった）
  const key = [title, article.thumbnail ?? "", article.coverImage ?? ""].join("|");
  return `/cover/${article.slug}?v=${COVER_VERSION}${key !== "||" ? `-${titleHash(key)}` : ""}`;
}

/**
 * 画像に赤い「速報」を付けてよい記事か。速報（主要企業の公式発表の速報。article.breaking）か、
 * 公式発表から60分以内に載せた記事（speedMinutes が入る）だけ。ほかは「ニュース」（2026-11-03 の画面の点検 B）
 */
export function isFastNews(article: { breaking?: boolean | null; speedMinutes?: number | null; type?: string | null }): boolean {
  if (article.type === "roundup") return false;
  return Boolean(article.breaking) || typeof article.speedMinutes === "number";
}
