import data from "@/content/pricing.json";
import { getCompany, OTHER } from "@/lib/companies";

/**
 * AI料金・日本対応の早見表（/ai-pricing）のデータ。scripts/pricing_table.py が作る content/pricing.json。
 * 数字はすべてサイソクの記事に書かれたもので、記事本文との一致を機械的に確かめてある。
 * JSON は小さいのでページに直接読み込む（Cloudflare の仮想 fs を通さない）。
 */
export type PriceItem = {
  id: string;
  kind: "plan" | "api";
  vendor: string;
  companySlug: string;
  product: string;
  plan: string | null;
  currency: "USD" | "JPY";
  /** 月額（plan） */
  monthly: number | null;
  /** 100万トークンあたり（api） */
  input: number | null;
  output: number | null;
  cachedInput: number | null;
  japan: "ok" | "partial" | "no" | "unknown";
  status: "available" | "limited" | "soon" | "demo" | null;
  free: boolean | null;
  /** 同じ系列に新しい版がある API モデル */
  legacy: boolean;
  source: { slug: string; title: string; publishedAt: string; quote: string };
  /** 日本対応の判定を別の記事から取ったとき、その記事 */
  verdictSource: string | null;
  /** この数字が書かれていた記事の数 */
  confirmedIn: number;
};

export type PricingData = {
  updatedAt: string;
  generatedAt: string;
  stats: {
    articlesScanned: number;
    candidateArticles: number;
    rowsVerified: number;
    rowsRejected: number;
    plans: number;
    apis: number;
  };
  items: PriceItem[];
};

/** 画面に渡す形（企業の色・名前つき。クライアント部品に渡せる値だけ） */
export type PriceRow = PriceItem & { color: string; companyName: string };

const pricing = data as unknown as PricingData;

export function getPricing(): PricingData {
  return pricing;
}

export function priceRows(): PriceRow[] {
  return pricing.items.map((item) => {
    const company = getCompany(item.companySlug);
    const known = company && company.slug !== OTHER.slug;
    return {
      ...item,
      color: known ? company.color : OTHER.color,
      companyName: known ? company.name : item.vendor || OTHER.name,
    };
  });
}

/** 記事が早見表の出典になっているか（記事ページから早見表へ案内するため） */
export function isPricingSource(slug: string): boolean {
  return pricing.items.some((item) => item.source.slug === slug || item.verdictSource === slug);
}

export { formatMoney, formatYen } from "@/lib/money";
