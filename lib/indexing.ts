import type { ArticleSummary } from "@/lib/articles";

/**
 * Google に見せる記事を選ぶ（サイトでは全記事を読める）。
 *
 * 文字数だけでは記事の有用性を判断できない。手動指定と配信元による既存の除外は維持し、
 * それ以外の記事は文字数にかかわらず検索対象にする。品質は制作・編集時に確認する。
 * scripts/indexnow.py の is_indexable と同じ基準にしておくこと。
 */

/** プレスリリースの配信サービス（量が多く、言い換えになりやすい） */
export const WIRE_SOURCES = new Set(["prtimes", "prtimes-all", "atpress", "value-press", "kyodo-prwire", "dreamnews"]);

export function isIndexable(article: ArticleSummary): boolean {
  // 手動で決めたものを優先（あとで反応の良い記事を検索に出す、などに使う）
  if (typeof article.indexable === "boolean") return article.indexable;
  // 動画・まとめ記事は従来どおり対象にする。
  if (article.sourceType !== "web" || article.type === "roundup") return true;
  // プレスリリースの配信は検索に出さない（2026-10-27 から新規の取得も停止）
  if (WIRE_SOURCES.has(article.channelSlug)) return false;
  // 本文がないweb記事を誤って検索へ出さない。短さ自体は判定しない。
  if (article.bodyLength === 0) return false;
  return true;
}

/** 外部配信・既存のメール等は、検索方針の変更による内容の急変を防ぎ従来基準を保持する。 */
export function isDistributionEligible(article: ArticleSummary): boolean {
  if (typeof article.indexable === "boolean") return article.indexable;
  if (article.sourceType !== "web" || article.type === "roundup") return true;
  if (WIRE_SOURCES.has(article.channelSlug)) return false;
  return article.bodyLength >= 2000;
}
