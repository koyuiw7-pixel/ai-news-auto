import type { Article } from "@/lib/articles";

/**
 * Google に見せる記事を選ぶ（サイトでは全記事を読める）。
 *
 * Google はサイト全体の平均の質を見るので、プレスリリースを言い換えただけの薄い記事まで見せると
 * 「量産で中身が薄いサイト」と判断されやすい。本数は保ったまま、検索には中身の濃い記事だけを出す。
 * scripts/indexnow.py の is_indexable と同じ基準にしておくこと。
 */

/** プレスリリースの配信サービス（量が多く、言い換えになりやすい） */
export const WIRE_SOURCES = new Set(["prtimes", "prtimes-all", "atpress", "value-press", "kyodo-prwire", "dreamnews"]);

export function isIndexable(article: Article): boolean {
  // 手動で決めたものを優先（あとで反応の良い記事を検索に出す、などに使う）
  if (typeof article.indexable === "boolean") return article.indexable;
  // 動画の解析記事・まとめ記事は独自の解説が厚い
  if (article.sourceType !== "web" || article.type === "roundup") return true;
  const length = article.body.length;
  // プレスリリースの配信は、十分に厚い記事だけ
  if (WIRE_SOURCES.has(article.channelSlug)) return length >= 3200;
  // 話題のニュース（複数の報道をまとめたもの）と、公式ブログ・官公庁・企業の一次情報
  return length >= 2000;
}
