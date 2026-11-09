import type { ArticleSummary } from "@/lib/articles";
import { actionAdRuleMatches } from "@/lib/action-ad";
import { actionAdRules, isRoundupArticle, partnerItem, type ActionAdRule, type OfferItem } from "@/lib/offers";
import { isFastNews } from "@/lib/cover-path";
import { isDisasterArticle } from "@/lib/related";
import { COMPARE_SLOT } from "@/lib/compare-slot";

/**
 * ニュース → 比較記事の導線（2026-11-09 オーナー「収益考えて」・Muse の調査 saisoku-reply-20261109-1200）。
 * 伸びているサイト（LIMO・MONEY PLUS・マイベスト）は、ニュースの横で売らず、ニュースで生まれた「選びたい」気持ちを
 * 常設の選び方・比較の記事へ送り、そこに公式リンク（A8）を置いている。サイソクも同じ形にする:
 *  - 比較記事: Muse のジャンル「比較」の記事（kind: "comparison"・comparisonTopic は actionAds の key）
 *  - ニュース記事: 「すぐにできること」の PR と同じ話題の判定（lib/action-ad.ts の actionAdRuleMatches）で当たり、
 *    その話題の比較記事が公開されていれば「次に読む」のカードを ①判断ガイドの直後（無ければすぐにできることの直後）②記事の終わりに出す。
 *    自分たちの記事への案内なので PR の札は付けず、広告の枠の数（本文の列に最大3つ）にも数えない。
 *  - 比較記事のページ: 話題の提携先を、比較表の直後と記事の終わりに「公式サイトで見る」つきの一覧で出す（PR の札・計測ピクセルつき）。
 */

export { COMPARE_SLOT };

type Kindish = Pick<ArticleSummary, "kind"> & { museFile?: string };

/** 選び方・比較の記事か（公開時の印。印の無い Muse の「比較」の原稿はファイル名で拾う） */
export function isComparison(article: Kindish): boolean {
  return article.kind === "comparison" || /^\d{8}-比較-/.test(article.museFile ?? "");
}

function hits(re: RegExp, text: string): number {
  const found = text.match(new RegExp(re.source, re.flags.includes("g") ? re.flags : `${re.flags}g`));
  return found ? new Set(found.map((w) => w.toLowerCase())).size : 0;
}

/**
 * 比較記事の話題（actionAds の key）。公開時に決めた comparisonTopic が無ければ、題名・本文から同じ規則で決める
 * （scripts/muse_articles.py の comparison_topic と同じ: 題名に当たる話題を優先し、当たった語の数・本文の語の数の多い順。同点は actionAds の順）
 */
export function comparisonTopicOf(
  article: Pick<ArticleSummary, "title" | "seoTitle" | "lede" | "description"> & { comparisonTopic?: string; body?: string },
  rules: ActionAdRule[] = actionAdRules(),
): string | undefined {
  if (article.comparisonTopic && rules.some((r) => r.key === article.comparisonTopic)) return article.comparisonTopic;
  const title = `${article.title} ${article.seoTitle ?? ""}`;
  const body = `${article.lede ?? ""} ${article.description ?? ""} ${article.body ?? ""}`;
  let best: { key: string; score: [number, number, number] } | undefined;
  for (const rule of rules) {
    let re: RegExp;
    try {
      re = new RegExp(rule.match, "i");
    } catch {
      continue;
    }
    if (rule.exclude && new RegExp(rule.exclude, "i").test(title)) continue;
    const t = hits(re, title);
    const b = hits(re, body);
    if (t === 0 && b < 3) continue;
    const score: [number, number, number] = [t > 0 ? 1 : 0, t, b];
    if (!best || score[0] > best.score[0] || (score[0] === best.score[0] && (score[1] > best.score[1] || (score[1] === best.score[1] && score[2] > best.score[2])))) {
      best = { key: rule.key, score };
    }
  }
  return best?.key;
}

/** ニュースの話題 → 案内してよい比較記事の話題（その話題の比較記事が無いときの近い受け皿） */
const NEAR_TOPICS: Record<string, string[]> = {
  "fire-insurance": ["disaster"],
  water: ["disaster"],
  household: ["energy", "mobile"],
  moving: ["mobile"],
  payment: ["household"],
};

/** カードの1行の理由（話題ごと。比較記事の中身を言い切らず、読者の次の一歩として書く） */
const REASONS: Record<string, string> = {
  leak: "流出した情報を使った詐欺や不正ログインが心配なら、対策ソフトの選び方を価格と機能で比べています",
  disaster: "停電や断水が続いたときの備えを、ポータブル電源・非常食・防災セットの中身と価格で比べています",
  energy: "電気代が気になるなら、契約先ごとの基本料金と単価の違いを比べています",
  mobile: "料金の変更や障害をきっかけに見直すなら、スマホと光回線の月額を公式の料金で比べています",
  furusato: "寄附の申込先を選ぶなら、サイトごとの違いと手続きを比べています",
  household: "固定費を見直すなら、スマホ代や電気代の契約の比べ方をまとめています",
  tax: "申告の準備を進めるなら、会計ソフトの選び方を比べています",
  kids: "子どもの学びの選択肢を、費用と内容で比べています",
  "fire-insurance": "保険の見直しを考えるなら、補償と保険料の比べ方をまとめています",
};

export type FunnelCard = {
  target: ArticleSummary;
  topic: string;
  reason: string;
  /** "both": 判断ガイドの直後と記事の終わり。"end": 記事の終わりだけ（地震・津波の速報や、速報の当日） */
  placement: "both" | "end";
};

/** 公開されている比較記事（話題 → 新しい順の1本目） */
export function comparisonByTopic(all: ArticleSummary[], rules: ActionAdRule[] = actionAdRules()): Map<string, ArticleSummary> {
  const map = new Map<string, ArticleSummary>();
  for (const a of all) {
    if (!isComparison(a) || a.duplicate || a.duplicateOf || a.indexable === false) continue;
    const topic = comparisonTopicOf(a, rules);
    if (topic && !map.has(topic)) map.set(topic, a); // all は新しい順
  }
  return map;
}

/**
 * ニュース記事に出す「次に読む」の比較記事（無ければ undefined）。
 * 話題の判定は「すぐにできること」の PR と同じ（題名に話題の語があり、関連の点数が基準点以上。まとめ記事には出さない）。
 * 当たった話題を actionAds の順に見て、その話題（無ければ近い話題）の比較記事が公開されている最初のものを使う。
 */
export function funnelForArticle(
  article: ArticleSummary,
  all: ArticleSummary[],
  rules: ActionAdRule[] = actionAdRules(),
  now: number = Date.now(),
): FunnelCard | undefined {
  if (isComparison(article as Kindish) || isRoundupArticle(article)) return undefined;
  const byTopic = comparisonByTopic(all, rules);
  if (byTopic.size === 0) return undefined;
  for (const rule of rules) {
    if (!actionAdRuleMatches(rule, article)) continue;
    for (const topic of [rule.key, ...(NEAR_TOPICS[rule.key] ?? [])]) {
      const target = byTopic.get(topic);
      if (!target || target.slug === article.slug) continue;
      const published = new Date(article.publishedAt).getTime();
      const fresh = isFastNews(article) && Number.isFinite(published) && now - published < 24 * 3600 * 1000;
      // 速報の当日と、地震・津波の速報（被害の渦中）は記事の終わりの1枠だけ（Muse の調査の決まり）
      const placement = isDisasterArticle(article) || fresh ? "end" : "both";
      return { target, topic, reason: REASONS[topic] ?? rules.find((r) => r.key === topic)?.reason ?? "選び方と違いを公式の情報で比べています", placement };
    }
  }
  return undefined;
}

export type CompareOffer = { item: OfferItem; pixel?: string; fit?: string };

const withFit = (key: string): CompareOffer | undefined => {
  const x = partnerItem(key);
  return x ? { ...x, fit: x.item.fit } : undefined;
};

/** 比較記事のページに出す提携先（話題の actionAds の partners の順。提携リンクのあるものだけ） */
export function compareOffersFor(
  article: Parameters<typeof comparisonTopicOf>[0] & Kindish,
  rules: ActionAdRule[] = actionAdRules(),
  pick: (key: string) => CompareOffer | undefined = withFit,
): { topic: string; title: string; items: CompareOffer[] } | undefined {
  if (!isComparison(article)) return undefined;
  const topic = comparisonTopicOf(article, rules);
  const rule = rules.find((r) => r.key === topic);
  if (!topic || !rule) return undefined;
  const items = rule.partners.map((key) => pick(key)).filter((x): x is CompareOffer => Boolean(x));
  if (items.length === 0) return undefined;
  return { topic, title: rule.title, items };
}

/** 比較記事の本文の最初の表の直後に印を入れる（ノワールの横スクロールの囲みは表だけを包むので、印は囲みの外に残る）。表が無ければそのまま */
export function insertCompareSlot(html: string): string {
  const re = /<table[\s>][\s\S]*?<\/table>/i;
  const m = re.exec(html);
  if (!m) return html;
  const end = m.index + m[0].length;
  return `${html.slice(0, end)}${COMPARE_SLOT}${html.slice(end)}`;
}
