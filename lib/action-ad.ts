import type { ArticleSummary } from "@/lib/articles";
import { actionAdRules, intentFor, isRoundupArticle, MIN_SCORE, orderByIntent, partnerItem, relevanceScore, type ActionAdRule, type OfferItem } from "@/lib/offers";

/**
 * 記事の「すぐにできること」（読者がこのあと取る行動）のすぐ下に出す、PR の囲み1つ。
 * 情報流出ならセキュリティソフト、地震・大雨なら停電・防災の備え、ふるさと納税なら寄附サイト…のように、
 * 行動と同じ話題の提携商品だけを出す（話題の対応は scripts/a8_import.py の ACTION_ADS → content/offers.json の actionAds）。
 * 見出しに話題の語があり、見出し・タグ・要約の点数（relevanceScore）が基準点（MIN_SCORE）を超えた最初の話題を使う。どれにも当たらなければ出さない。
 */
export type ActionAd = {
  key: string;
  title: string;
  reason?: string;
  /** 記事から商品へつなぐ編集部の一文（場面の lead → 話題の lead） */
  lead?: string;
  /** 当たった場面（停電・地震など）。無ければ undefined */
  intent?: string;
  items: { item: OfferItem; pixel?: string }[];
};

function hashOf(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0;
  return h;
}

/** 話題1つが記事に当たるか（ジャンル・除く語・見出しに話題の語・関連の点数が基準点以上）。比較記事への案内（lib/comparison.ts）も同じ判定を使う */
export function actionAdRuleMatches(rule: ActionAdRule, article: ArticleSummary): boolean {
  const title = `${article.title} ${article.seoTitle ?? ""}`;
  if (rule.genres && !rule.genres.includes(article.genreSlug)) return false;
  if (rule.exclude && new RegExp(rule.exclude, "i").test(title)) return false;
  // 見出しに話題の語があること（タグや要約の脇の1語だけで当てない）
  let re: RegExp;
  try {
    re = new RegExp(rule.match, "i");
  } catch {
    return false;
  }
  return re.test(title) && relevanceScore(rule.match, article) >= MIN_SCORE;
}

/** 記事に合う話題（無ければ undefined）。rules を渡せば設定ファイルを読まずに使える（テスト用） */
export function actionAdRuleFor(article: ArticleSummary, rules: ActionAdRule[] = actionAdRules()): ActionAdRule | undefined {
  // まとめ記事（「…の発表まとめ、詐欺対策も」など）は脇の1語で当たるので出さない
  if (isRoundupArticle(article)) return undefined;
  return rules.find((rule) => actionAdRuleMatches(rule, article));
}

/**
 * 記事に出す PR。提携リンクのある商品だけ、最大 max 件（既定2件）。
 * 右側の枠（avoid）に出ている商品は後ろに回す。並びは記事ごとにずらし、表示が1社に偏らないようにする
 */
export function actionAdForArticle(
  article: ArticleSummary,
  avoid: Iterable<string> = [],
  pick: (key: string) => { item: OfferItem; pixel?: string } | undefined = partnerItem,
  rules?: ActionAdRule[],
): ActionAd | undefined {
  const rule = actionAdRuleFor(article, rules);
  if (!rule) return undefined;
  // 記事の場面（停電・地震など）に当たれば、その場面の商品を先頭に固定する（記事ごとにずらさない）。
  // 当たらなければ今までどおり記事ごとにずらし、表示が1社に偏らないようにする
  const intent = intentFor(rule.intents, article);
  const available = orderByIntent(rule.partners, intent).map((key) => pick(key)).filter((x): x is { item: OfferItem; pixel?: string } => Boolean(x));
  if (available.length === 0) return undefined;
  const start = intent ? 0 : hashOf(article.slug) % available.length;
  const rotated = [...available.slice(start), ...available.slice(0, start)];
  const skip = new Set(avoid);
  const ordered = [...rotated.filter((x) => !skip.has(x.item.key)), ...rotated.filter((x) => skip.has(x.item.key))];
  return { key: rule.key, title: rule.title, reason: rule.reason, lead: intent?.lead ?? rule.lead, intent: intent?.key, items: ordered.slice(0, rule.max ?? 2) };
}
