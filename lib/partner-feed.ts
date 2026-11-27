import { AI_TOPIC, isDistributionEligible, isDuplicateArticle, isIndexable, lifeLink } from "@/lib/indexing";
import { noReaderAction } from "@/lib/reader-urgency";
import { LIFE_MONEY_GENRES } from "@/lib/home-lead";
import { getAllArticles, getArticle, type ArticleSummary, type FullArticle } from "@/lib/articles";

/**
 * ニュースアプリ（グノシー・スマートニュース、あとで Yahoo!ニュース・LINE NEWS・MSN）へ送る記事の選び方（2026-11-28）。
 * 新しい方向「あなたの数字のニュース」（out/strategy_20261128/review_ja.md）に合わせ、暮らしとお金の記事だけを送る。
 *
 * 載せる記事:
 *  - 暮らしとお金の分野（lib/home-lead.ts の LIFE_MONEY_GENRES: 社会・行政／暮らし／投資・マネー／ビジネス・経済／不動産）
 *  - 題名がお金か暮らしにつながる（lib/indexing.ts の lifeLink）。面会・式典・人事など読者がすることの無い発表は外す
 *  - AI・テクノロジーの話題（AI_TOPIC）、海外の話題（題名に海外の国・通貨）は外す。スポーツ・芸能は分野で外れる
 *  - 検索に出している記事（isIndexable。noindex の記事は送らない）で、従来の外部配信の基準（isDistributionEligible）も満たす
 *  - まとめ・重複・比較ページ（kind: comparison。紹介リンクが中心）・未来の日時の記事は外す
 *
 * 本文は広告・紹介リンク・PR の囲み・計測の画像を含まない（lib/feeds.ts の feedProblems で最後に確かめ、残っていたらその記事ごと外す）。
 */

/** 題名に出ると海外の話題とみなす語（日本の暮らしに直接かかわらないことが多い） */
const OVERSEAS = /米国|アメリカ|米政府|米大統領|トランプ|中国|韓国|台湾|欧州|(?<![A-Za-z])EU(?![A-Za-z])|英国|イギリス|ドイツ|フランス|インド|ロシア|海外|(?<![\d,.])\d[\d,.]*(?:万|億)?ドル|ユーロ/;

/** 載せない理由（載せるなら null）。テストと確認用に理由を返す */
export function partnerAxisReason(a: ArticleSummary): string | null {
  if (a.type === "roundup") return "roundup";
  if (a.kind === "comparison") return "comparison";
  if (isDuplicateArticle(a)) return "duplicate";
  if (!LIFE_MONEY_GENRES.has(a.genreSlug)) return "genre";
  const title = (a.title ?? "").normalize("NFKC");
  if (AI_TOPIC.test(`${title} ${(a.tags ?? []).join(" ")}`)) return "ai-tech";
  if (OVERSEAS.test(title)) return "overseas";
  if (!lifeLink(title) || noReaderAction(title)) return "off-axis";
  if (!isIndexable(a)) return "noindex";
  if (!isDistributionEligible(a)) return "distribution";
  return null;
}

export const isPartnerArticle = (a: ArticleSummary) => partnerAxisReason(a) === null;

const publishedAt = (a: ArticleSummary) => Date.parse(a.generatedAt || a.publishedAt);

/**
 * 配信先へ送る記事（新しい順・本文つき）。maxAgeDays より古い記事は配信先が取り込まないので載せない。
 * minItems に届かないときだけ、古い記事で minItems まで埋める（スマートニュースの「常に5本以上」）
 */
export function pickPartnerArticles({
  limit,
  maxAgeDays,
  minItems = 0,
  now = Date.now(),
}: {
  limit: number;
  maxAgeDays: number;
  minItems?: number;
  now?: number;
}): FullArticle[] {
  const published = getAllArticles()
    .filter(isPartnerArticle)
    .filter((a) => {
      const at = publishedAt(a);
      return Number.isFinite(at) && at <= now;
    });
  const fresh = published.filter((a) => now - publishedAt(a) < maxAgeDays * 86_400_000);
  const chosen = (fresh.length >= minItems ? fresh : published.slice(0, minItems)).slice(0, limit);
  return chosen.map((a) => getArticle(a.slug)).filter((a): a is FullArticle => Boolean(a));
}
