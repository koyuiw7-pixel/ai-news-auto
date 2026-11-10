import type { ActionAd } from "@/lib/action-ad";
import { actionAdRules, partnerItem, type ActionAdRule, type OfferItem } from "@/lib/offers";

/**
 * 手続きガイド（/guides/*。content/howto の kind: "procedure"）と計算ツールに出す PR の囲み（2026-11-10）。
 *
 * ガイドの話題と同じ提携商品だけを出す。話題は記事の PR（lib/action-ad.ts）と同じ設定（content/offers.json の actionAds）のうち、
 * 下の3つだけを使う。どれにも当たらないガイドには何も出さない（AIツールの使い方ガイドには出さない）。
 *  - furusato: ふるさと納税 → ふるさと納税のサイト
 *  - tax: 年末調整・確定申告 → 確定申告ソフト
 *  - mobile: スマホの乗り換え → 格安SIM（光回線は乗り換えの手順と話題が違うので出さない）
 * NISA のガイドには出さない（投資の広告は置かない）。化粧品・健康食品・ギャンブル・ローンなどの話題は、この一覧に入れない。
 *
 * 当て方: ガイドの見出し（title・seoTitle）と検索語（keyword）に話題の語があること。本文の脇の1語では当てない。
 * 上の囲み（結論・導入のすぐ下）は、見出しでいちばん先に出てくる話題。下の囲み（よくある質問の前）は、2つ目の話題があればそれ、
 * 無ければ同じ話題で先頭の商品を入れ替えたもの。
 */
type GuideRule = {
  /** content/offers.json の actionAds の key */
  key: string;
  /** ガイドだけで足す語（記事の PR の語に無い、同じ話題の手続きの名前） */
  extra?: RegExp;
  /** この話題でガイドに出す商品を絞るとき（無ければ話題の商品すべて） */
  partners?: string[];
};

export const GUIDE_AD_RULES: GuideRule[] = [
  { key: "furusato" },
  // 還付申告・事業所得・雑所得は、どれも確定申告で申告する
  { key: "tax", extra: /還付申告|事業所得|雑所得/ },
  { key: "mobile", partners: ["bb-excite"] },
];

/** 置き場所の名前（data-aff-pos。cloudflare/aff.ts は末尾の「-数字」を順番として外すので、数字で終わらせない） */
export const GUIDE_AD_POS = { top: "guide-top", lower: "guide-lower", tool: "tool-result" } as const;

export type GuideAdTarget = { slug: string; kind?: string; tool?: string; title: string; seoTitle?: string; keyword?: string };
type Picked = { item: OfferItem; pixel?: string };
type Pick = (key: string) => Picked | undefined;

function hashOf(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0;
  return h;
}

function patternOf(rule: ActionAdRule, extra?: RegExp): RegExp | undefined {
  try {
    return new RegExp(extra ? `${rule.match}|${extra.source}` : rule.match, "i");
  } catch {
    return undefined;
  }
}

type Matched = { rule: ActionAdRule; partners: string[]; at: number };

/** ガイドに当たる話題（見出しで先に出てくる順）。ふるさと納税のガイド（tool: "furusato"）は、ふるさと納税を先頭にする */
export function guideAdRulesFor(guide: GuideAdTarget, rules: ActionAdRule[] = actionAdRules()): Matched[] {
  if (guide.kind !== "procedure") return [];
  const title = `${guide.title} ${guide.seoTitle ?? ""}`;
  const text = `${title} ${guide.keyword ?? ""}`;
  const matched: Matched[] = [];
  for (const config of GUIDE_AD_RULES) {
    const rule = rules.find((r) => r.key === config.key);
    const re = rule ? patternOf(rule, config.extra) : undefined;
    if (!rule || !re || !re.test(text)) continue;
    const index = title.search(re);
    const first = config.key === "furusato" && guide.tool === "furusato";
    matched.push({ rule, partners: config.partners ?? rule.partners, at: first ? -1 : index < 0 ? Number.MAX_SAFE_INTEGER : index });
  }
  return matched.sort((a, b) => a.at - b.at);
}

function adOf(rule: ActionAdRule, items: Picked[]): ActionAd | undefined {
  if (items.length === 0) return undefined;
  return { key: rule.key, title: rule.title, reason: rule.reason, lead: rule.lead, items: items.slice(0, rule.max ?? 2) };
}

function rotate<T>(list: T[], start: number): T[] {
  if (list.length === 0) return list;
  const s = start % list.length;
  return [...list.slice(s), ...list.slice(0, s)];
}

/**
 * ガイドに出す PR（上・下）。提携リンクのある商品だけ（pick が undefined を返す商品は出さない）。
 * 並びはガイドごとにずらし、表示が1社に偏らないようにする。同じ商品の表示の計測（pixel）は、上の囲みで1回だけ数える。
 */
export function guideAds(guide: GuideAdTarget, pick: Pick = partnerItem, rules?: ActionAdRule[]): { top?: ActionAd; lower?: ActionAd } {
  const matched = guideAdRulesFor(guide, rules);
  if (matched.length === 0) return {};
  const available = (m: Matched) => m.partners.map((key) => pick(key)).filter((x): x is Picked => Boolean(x));
  const [primary, secondary] = matched;
  const first = available(primary);
  const start = first.length > 0 ? hashOf(guide.slug) % first.length : 0;
  const top = adOf(primary.rule, rotate(first, start));
  const shown = new Set((top?.items ?? []).map(({ item }) => item.key));
  const second = secondary ? available(secondary) : [];
  const lowerItems =
    second.length > 0
      ? rotate(second, hashOf(guide.slug) % second.length)
      : // 同じ話題をもう一度出すときは、上の囲みで先頭でなかった商品を先頭にする
        rotate(first, start + Math.max(1, Math.min(primary.rule.max ?? 2, first.length - 1)));
  const lowerRule = second.length > 0 ? secondary.rule : primary.rule;
  const lower = adOf(
    lowerRule,
    lowerItems.map((x) => (shown.has(x.item.key) ? { item: x.item } : x)),
  );
  if (!top) return lower ? { top: lower } : {};
  return { top, lower };
}

/** 計算ツールの結果のそばに出す PR（話題1つ。例: ふるさと納税の上限額のページ → ふるさと納税のサイト） */
export function toolAd(ruleKey: string, pick: Pick = partnerItem, rules: ActionAdRule[] = actionAdRules()): ActionAd | undefined {
  if (!GUIDE_AD_RULES.some((config) => config.key === ruleKey)) return undefined;
  const rule = rules.find((r) => r.key === ruleKey);
  if (!rule) return undefined;
  const config = GUIDE_AD_RULES.find((c) => c.key === ruleKey);
  return adOf(rule, (config?.partners ?? rule.partners).map((key) => pick(key)).filter((x): x is Picked => Boolean(x)));
}
