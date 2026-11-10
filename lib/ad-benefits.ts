import data from "@/content/ad_benefits.json";

/**
 * 広告の「得のカード」の中身（content/ad_benefits.json。台帳 W38）。
 * 2026-11-10 オーナー「説明ちっくじゃダメ、直感的に見てわかる状態に」「約いくらみたいな感じ」「提携している広告の魅力を上げる作戦を記事ごとに」:
 *  - chips: 一目で分かる大きな数字（料金・自己負担・無料の期間など。3つまで）。数字はすべて公式ページの出典（url・確認日）つき
 *  - points: 数字で語れない広告の「これで何が防げる／何が手に入る」（3つまで。chips が無いとき PrFeature は従来の良いところ＝merits を出す）
 *  - compare: 前と後の比べ（どちらも出典のある数字だけ）。棒の長さで差を見せる
 *  - headline: 記事ごとの見出し（読者の状況を呼ぶ）。articles の match（slug の正規表現）で決める
 * 守ること（景品表示法の優良誤認・有利誤認）: 出典の無い数字は出さない（ここで捨てる）。「最安」「必ず」「絶対」「No.1」「一番」は使わない
 */

export type BenefitSource = { name: string; url: string; checkedAt: string };
export type BenefitChip = { label: string; value: string; sub?: string; source: BenefitSource };
export type BenefitCompare = { label: string; rows: { name: string; value: number; text: string }[]; source: BenefitSource };
export type Benefit = {
  headline?: string;
  /** 誰向けか（平易な1行。content/ad_benefits.json の offers の who。得のカードの A/B の上の行に使う。lib/ad-ab.ts） */
  who?: string;
  chips: BenefitChip[];
  points: string[];
  compare?: BenefitCompare;
  /** サイト内の案内（計算ツールなど。広告ではない） */
  link?: { href: string; label: string };
  /** カードの下に出す出典（重なりなし） */
  sources: BenefitSource[];
};

type RawChip = { label: string; value: string; sub?: string; src: string };
type RawOffer = {
  use?: string;
  who?: string;
  chips?: RawChip[];
  points?: string[];
  compare?: { label: string; rows: { name: string; value: number; text: string }[]; src: string };
  link?: { href: string; label: string };
};
type RawFile = {
  sources: Record<string, BenefitSource>;
  offers: Record<string, RawOffer>;
  articles: { match: string; headlines: Record<string, string> }[];
};

const FILE = data as unknown as RawFile;

/** 景品表示法で根拠なしに使えない言葉 */
export const BANNED_WORDS = /最安|必ず|絶対|No\.?\s?1|ナンバーワン|一番|日本一|業界初/i;

function validSource(source: BenefitSource | undefined): source is BenefitSource {
  return Boolean(source && source.name && /^(https:\/\/|\/)/.test(source.url) && /^\d{4}-\d{2}-\d{2}$/.test(source.checkedAt));
}

function clean(text: string | undefined): string | undefined {
  return text && !BANNED_WORDS.test(text) ? text : undefined;
}

function rawOf(key: string): RawOffer | undefined {
  const raw = FILE.offers[key];
  if (raw?.use) return FILE.offers[raw.use];
  return raw;
}

/** 記事ごとの見出し（context＝「slug 題名」が match に合う最初の行。その商品の見出しが無い行は飛ばす。無ければ undefined） */
export function articleHeadline(key: string, slug: string | undefined): string | undefined {
  if (!slug) return undefined;
  for (const row of FILE.articles) {
    let re: RegExp;
    try {
      re = new RegExp(row.match);
    } catch {
      continue;
    }
    if (re.test(slug) && row.headlines[key]) return clean(row.headlines[key]);
  }
  return undefined;
}

/** 提携商品 key の得のカード。数字も見出しも無ければ undefined（従来の囲みのまま） */
export function benefitFor(key: string, slug?: string): Benefit | undefined {
  const raw = rawOf(key);
  const headline = articleHeadline(key, slug);
  if (!raw && !headline) return undefined;
  const sources: BenefitSource[] = [];
  const addSource = (s: BenefitSource) => {
    if (!sources.some((x) => x.url === s.url)) sources.push(s);
  };
  const chips: BenefitChip[] = [];
  for (const chip of raw?.chips ?? []) {
    const source = FILE.sources[chip.src];
    if (!validSource(source) || !clean(chip.label) || !clean(chip.value) || (chip.sub && !clean(chip.sub))) continue;
    chips.push({ label: chip.label, value: chip.value, sub: chip.sub || undefined, source });
    addSource(source);
    if (chips.length === 3) break;
  }
  let compare: BenefitCompare | undefined;
  if (raw?.compare) {
    const source = FILE.sources[raw.compare.src];
    const rows = raw.compare.rows.filter((r) => Number.isFinite(r.value) && r.value >= 0 && clean(r.name) && clean(r.text));
    if (validSource(source) && rows.length >= 2 && clean(raw.compare.label)) {
      compare = { label: raw.compare.label, rows, source };
      addSource(source);
    }
  }
  const points = (raw?.points ?? []).filter((p) => clean(p)).slice(0, 3);
  if (!headline && chips.length === 0 && !compare && points.length === 0) return undefined;
  return { headline, ...(raw?.who && clean(raw.who) ? { who: raw.who } : {}), chips, points, compare, link: raw?.link, sources };
}

/** 記事の枠の商品に、その記事の見出しを入れた得のカードを付け直す（枠の中身・順番・置き場所は変えない） */
export function withArticleBenefits<T extends { item: { key: string; benefit?: Benefit } }>(list: T[], slug: string): T[] {
  return list.map((entry) => {
    const benefit = benefitFor(entry.item.key, slug);
    return benefit ? { ...entry, item: { ...entry.item, benefit } } : entry;
  });
}

/** OfferItem だけの一覧（枠の items が OfferItem の配列のとき） */
export function itemsWithArticleBenefits<T extends { key: string; benefit?: Benefit }>(items: T[], slug: string): T[] {
  return items.map((item) => {
    const benefit = benefitFor(item.key, slug);
    return benefit ? { ...item, benefit } : item;
  });
}

/** 行動欄の PR（lib/action-ad.ts の ActionAd）に得のカードを付ける */
export function actionAdWithBenefits<T extends { items: { item: { key: string; benefit?: Benefit } }[] }>(ad: T | undefined, slug: string): T | undefined {
  return ad ? { ...ad, items: withArticleBenefits(ad.items, slug) } : ad;
}

/** 商品枠（lib/offers.ts の Offer）に得のカードを付ける */
export function offerWithBenefits<T extends { items: { key: string; benefit?: Benefit }[] }>(offer: T | undefined, slug: string): T | undefined {
  return offer ? { ...offer, items: itemsWithArticleBenefits(offer.items, slug) } : offer;
}
