import type { ActionAd } from "@/lib/action-ad";
import { MONEY_PAGES, type MoneyTarget } from "@/lib/money-pages";
import { actionAdRules, partnerItem, partnerKeysMatching, type ActionAdRule, type OfferItem } from "@/lib/offers";

/**
 * 手続きガイド（/guides/*。content/howto の kind: "procedure"）と計算ツールに出す PR の囲み（2026-11-10）。
 *
 * ガイドの話題と同じ提携商品だけを出す。話題は記事の PR（lib/action-ad.ts）と同じ設定（content/offers.json の actionAds）のうち、
 * 下の3つだけを使う。どれにも当たらないガイドには何も出さない（AIツールの使い方ガイドには出さない）。
 *  - furusato: ふるさと納税 → ふるさと納税のサイト
 *  - tax: 年末調整・確定申告 → 確定申告ソフト
 *  - mobile: スマホの乗り換え → 格安SIM（光回線は乗り換えの手順と話題が違うので出さない）
 *  - kids: 児童手当 → 子どもの学び（上）とふるさと納税のサイト＋上限額の計算への案内（下）（2026-11-10 M3）
 *  - medical: 高額療養費 → サイト内の案内（医療費控除のガイドと多数回該当の記事）だけ。保険相談の提携先が offers.json に入れば、同じ囲みに並ぶ
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
  /** true なら話題の語（記事の PR の match）を使わず、extra だけで当てる（子育ての広い語で、別の手続きのガイドに当てない） */
  only?: boolean;
  /** 名前か短い説明がこれに当たる提携商品も出す（あとから offers.json に足した提携先が、ガイドを直さずに並ぶ） */
  partnerMatch?: RegExp;
  /** 囲みの1行目に出すサイト内の案内（lib/money-pages.ts の行き先と、同じ話題の記事。広告ではない） */
  internal?: MoneyTarget[];
  /** 囲みの見出しとつなぎの一文を、記事の PR と変えるとき（案内だけの囲みなど） */
  title?: string;
  lead?: string;
  /** 下の囲み（よくある質問の前）に出す話題（offers.json の actionAds の key）と、その囲みの1行目の案内 */
  lower?: { key: string; internal?: MoneyTarget[] };
};

const moneyRow = (key: string) => MONEY_PAGES.find((row) => row.key === key);
const targetOf = (key: string): MoneyTarget[] => {
  const row = moneyRow(key);
  return row ? [{ href: row.href, label: row.label }] : [];
};
const secondOf = (key: string): MoneyTarget[] => {
  const second = moneyRow(key)?.second;
  return second ? [second] : [];
};

export const GUIDE_AD_RULES: GuideRule[] = [
  { key: "furusato" },
  // 還付申告・事業所得・雑所得は、どれも確定申告で申告する
  { key: "tax", extra: /還付申告|事業所得|雑所得/ },
  { key: "mobile", partners: ["bb-excite"] },
  // 児童手当のガイド: 上は子どもの学び（記事の PR でクリックがあった提携先）、下はふるさと納税のサイトと上限額の計算（12月31日まで）
  { key: "kids", extra: /児童手当/, only: true, lower: { key: "furusato", internal: targetOf("furusato") } },
  // 高額療養費のガイド: 合う提携先（保険相談）がまだ無いので、サイト内の案内だけ。格安SIM は出さない
  {
    key: "medical",
    extra: /高額療養費/,
    only: true,
    partners: [],
    partnerMatch: /保険相談|保険の相談/,
    internal: [...secondOf("kogaku-ryoyohi"), { href: "/articles/kogaku-ryoyohi-2026-tasukai-kaisu", label: "4回目からの上限額（多数回該当）を確かめる" }],
    title: "高額療養費を確かめたら、あわせて確かめること",
    lead: "医療費が多かった年は、確定申告で医療費控除を受けられる場合があります。",
  },
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

function patternOf(rule: ActionAdRule, extra?: RegExp, only = false): RegExp | undefined {
  try {
    if (only && extra) return new RegExp(extra.source, "i");
    return new RegExp(extra ? `${rule.match}|${extra.source}` : rule.match, "i");
  } catch {
    return undefined;
  }
}

type Matched = { rule: ActionAdRule; partners: string[]; at: number; config: GuideRule };

/** ガイドに当たる話題（見出しで先に出てくる順）。ふるさと納税のガイド（tool: "furusato"）は、ふるさと納税を先頭にする */
export function guideAdRulesFor(guide: GuideAdTarget, rules: ActionAdRule[] = actionAdRules(), matchPartners: (pattern: RegExp) => string[] = partnerKeysMatching): Matched[] {
  if (guide.kind !== "procedure") return [];
  const title = `${guide.title} ${guide.seoTitle ?? ""}`;
  const text = `${title} ${guide.keyword ?? ""}`;
  const matched: Matched[] = [];
  for (const config of GUIDE_AD_RULES) {
    const rule = rules.find((r) => r.key === config.key);
    const re = rule ? patternOf(rule, config.extra, config.only) : undefined;
    if (!rule || !re || !re.test(text)) continue;
    const index = title.search(re);
    const first = config.key === "furusato" && guide.tool === "furusato";
    const extraPartners = config.partnerMatch ? matchPartners(config.partnerMatch) : [];
    const partners = [...new Set([...(config.partners ?? rule.partners), ...extraPartners])];
    matched.push({ rule, partners, config, at: first ? -1 : index < 0 ? Number.MAX_SAFE_INTEGER : index });
  }
  return matched.sort((a, b) => a.at - b.at);
}

function adOf(rule: ActionAdRule, items: Picked[], config?: { internal?: MoneyTarget[]; title?: string; lead?: string }): ActionAd | undefined {
  const internal = config?.internal ?? [];
  if (items.length === 0 && internal.length === 0) return undefined;
  return {
    key: rule.key,
    title: config?.title ?? rule.title,
    reason: rule.reason,
    lead: config?.lead ?? rule.lead,
    items: items.slice(0, rule.max ?? 2),
    ...(internal.length ? { internal } : {}),
  };
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
export function guideAds(
  guide: GuideAdTarget,
  pick: Pick = partnerItem,
  rules?: ActionAdRule[],
  matchPartners?: (pattern: RegExp) => string[],
): { top?: ActionAd; lower?: ActionAd } {
  const matched = guideAdRulesFor(guide, rules, matchPartners);
  if (matched.length === 0) return {};
  const available = (m: Matched) => m.partners.map((key) => pick(key)).filter((x): x is Picked => Boolean(x));
  const [primary, secondary] = matched;
  const first = available(primary);
  const start = first.length > 0 ? hashOf(guide.slug) % first.length : 0;
  const top = adOf(primary.rule, rotate(first, start), primary.config);
  const shown = new Set((top?.items ?? []).map(({ item }) => item.key));
  // 下の囲みの話題をガイドの決まりで決めているとき（児童手当 → ふるさと納税）
  const lowerConfig = primary.config.lower;
  if (lowerConfig) {
    const rule = (rules ?? actionAdRules()).find((r) => r.key === lowerConfig.key);
    const items = rule ? rule.partners.map((key) => pick(key)).filter((x): x is Picked => Boolean(x)) : [];
    const lower = rule ? adOf(rule, rotate(items, hashOf(guide.slug) % Math.max(1, items.length)).map((x) => (shown.has(x.item.key) ? { item: x.item } : x)), { internal: lowerConfig.internal }) : undefined;
    if (!top) return lower ? { top: lower } : {};
    return lower ? { top, lower } : { top };
  }
  // 提携商品の無い案内だけの囲みは、下にもう一度出さない
  if (top && top.items.length === 0) return { top };
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
