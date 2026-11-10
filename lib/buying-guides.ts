import fs from "@/lib/content-fs";
import path from "node:path";
import { getArticleSummary, type ArticleSummary } from "@/lib/articles";
import { partnerItem, type OfferItem } from "@/lib/offers";
import { withoutNoData, withoutNoDataList } from "@/lib/no-data";
import { politeDeep } from "@/lib/polite-text";

/**
 * 比較ガイド（content/buying-guides/*.json）。scripts/buying_guides.py が作る。
 * 商品名・画像・リンクは offers.json と affiliate_links.json から毎回引く（提携が切れた商品は自動で消える）。
 */

export type PriceSource =
  | { type: "official"; url: string; checkedAt: string }
  | { type: "data"; file: string; checkedAt: string }
  | null;

/** サイソク判定の段階（公式の記載から機械的に決める。点数ではない） */
export type VerdictLevel = "yes" | "partial" | "no";

export type BuyingGuideProduct = {
  /** 提携商品は offers.json の partners のキー。提携していない商品（公式サイトへ nofollow で案内）は省略 */
  partner?: string;
  /** 新形式（schemaVersion 2）の識別子。省略時は partner を使う */
  id?: string;
  /** 提携していない商品の表示名（提携商品は offers.json の name を使う） */
  name?: string;
  maker?: string;
  /** 写真の代わりに出す種別（例: iPhone標準アプリ） */
  category?: string;
  price: string;
  priceSource: PriceSource;
  priceNote?: string;
  /** 旧形式の比較表の列（columns と同じ順）。新形式では cells を使う */
  specs?: string[];
  bestFor: string;
  summary: string;
  strengths: string[];
  limits: string[];
  officialUrl?: string;
  /** 以下は新形式のみ */
  verdict?: {
    japan: { level: VerdictLevel; text: string };
    freeTrial: { level: VerdictLevel; text: string };
    cost: string;
    bestFor: string;
  };
  /** 比較表の値（rows の key ごと） */
  cells?: Record<string, string>;
  /** 診断チャートの絞り込みに使う当てはまり（quiz の key → value の一覧） */
  fit?: Record<string, string[]>;
  sources?: { label: string; url: string }[];
};

/**
 * 比較ページの「絞り込み・並べ替え・あなたに合うのは」（components/compare/PlanFinder.tsx。2026-11-11 COMPARE-2）。
 * 数字はすべて各社の公式ページの記載（税込）。表の値は「段（データ量や住まい）× 条件（通話など）」ごとに、条件を満たす
 * いちばん安いプランを、データを作るときに計算して持つ（読者の画面では並べ替えるだけ）。提携先かどうかで順番は変えない。
 */
export type PlanFinderCell = { yen: number; label: string; gb?: number | null } | null;

export type PlanFinderItem = {
  /** products の id（提携商品は partner）と同じ */
  id: string;
  /** 種別（大手のサブブランド・格安SIM など） */
  kind: string;
  /** 絞り込みの札（回線など） */
  tags: string[];
  /** 段の key → 条件の key → いちばん安いプラン（無ければ null） */
  matrix: Record<string, Record<string, PlanFinderCell>>;
  /** 初めにかかる費用（税込。分からなければ null） */
  initialYen: number | null;
  /** くわしく（通話料・5G・解約など） */
  facts: { label: string; value: string }[];
  /** 発表済みの料金の変更（例: 12月1日から） */
  change?: string;
};

export type PlanFinder = {
  /** 金額の単位の説明（例: 月額・税込・割引なし） */
  unit: string;
  tierQuestion: string;
  tiers: { key: string; label: string }[];
  optionQuestion?: string;
  options?: { key: string; label: string }[];
  tagQuestion: string;
  tags: string[];
  /** 「こだわらない」の文 */
  anyTag: string;
  /** 並び順の決まり（ページに必ず出す） */
  sortRule: string;
  /** initialYen の呼び名（省略時は「初めの費用」。光回線は「事務手数料」） */
  initialLabel?: string;
  items: PlanFinderItem[];
};

export type BuyingGuide = {
  /** 2 = 提携外の商品も含めて手で作った新形式 */
  schemaVersion?: number;
  slug: string;
  title: string;
  /** 「〇〇を選ぶなら」に使う短い名前 */
  shortName?: string;
  description: string;
  targetQueries: string[];
  /** offers.json の話題キー。記事ページから案内するのに使う */
  topics: string[];
  intro: string;
  criteria: string[];
  columns: string[];
  products: BuyingGuideProduct[];
  quickPick: { partner: string; reason: string }[];
  faq: { q: string; a: string }[];
  relatedArticleSlugs: string[];
  publishedAt: string;
  updatedAt: string;
  priceCheckedAt: string;
  /** 以下は新形式のみ */
  /** 価格・仕様の時点と出典の表記（例: 10月27日時点・公式サイトより） */
  checkedLabel?: string;
  personas?: { who: string; picks: string[]; why: string }[];
  rows?: { key: string; label: string }[];
  decisionPoints?: { title: string; body: string }[];
  quiz?: { key: string; label: string; options: { value: string; label: string }[] }[];
  howWeMade?: string;
  editorial?: "manual";
  /** 「最新ニュース」の注記（省略時は従来の文） */
  newsNote?: string;
  /** 提携商品のボタンの文（省略時は「公式ストアで見る」） */
  sponsoredCta?: string;
  /** 向いている人・向いていない人の表（状況 → おすすめ → 理由 → 出典）。読者の得を先に書く */
  fitTable?: { situation: string; fit: "suits" | "not"; recommendation: string; reason: string; source: { label: string; url: string } }[];
  /** 公的機関の案内（総務省・資源エネルギー庁など。開けることを確かめた URL だけ） */
  officialGuidance?: { label: string; url: string; note: string }[];
  /**
   * 本題とは別の囲み（例: 保険相談のページの「火災保険」）。ここに挙げた商品は、比較表・判定・詳細の一覧には入れず、この囲みだけに出す
   */
  sideSections?: { id: string; label: string; title: string; body: string; products: string[] }[];
  /** 絞り込み・並べ替え・「あなたに合うのは」。あるときは比較表と「1つずつ見る」の代わりに出す */
  planFinder?: PlanFinder;
};

/** 表示用：ガイドの商品に提携リンクを合わせたもの */
export type ResolvedProduct = BuyingGuideProduct & {
  /** ページ内で商品を指す安定したキー */
  key: string;
  item: OfferItem;
  pixel?: string;
  /** 提携商品（PR表記・rel="sponsored"） */
  sponsored: boolean;
};

const DIR = path.join(/*turbopackIgnore: true*/ process.cwd(), "content", "buying-guides");

let cache: BuyingGuide[] | null = null;

/**
 * 比較ガイドを公開（検索・メニュー・記事からの導線）するか。
 * 中身とデザインを作り直すまでは false：ページは残すが検索には出さず、導線も出さない。
 */
export const COMPARE_PUBLIC = false;

/**
 * 暮らしとお金の比較ページ（格安SIM・光回線・電気とガス・保険相談・ふるさと納税サイト）。
 * COMPARE_PUBLIC を変えずに（検索・サイトマップには出さないまま）、記事のお金の囲みや入口から案内してよいページの一覧。
 * 検索に出すかどうかはオーナーが決める（COMPARE_PUBLIC と app/compare/[slug] の robots はそのまま）。
 */
export const LIFE_COMPARE_SLUGS = ["kakuyasu-sim", "hikari", "denki-gas", "hoken-soudan", "furusato-sites"] as const;
export type LifeCompareSlug = (typeof LIFE_COMPARE_SLUGS)[number];

export function isLifeCompareSlug(slug: string): slug is LifeCompareSlug {
  return (LIFE_COMPARE_SLUGS as readonly string[]).includes(slug);
}

/** サイト内から案内する比較ページ（LIFE_COMPARE_SLUGS のうち、いま表示できるものだけ） */
export function lifeCompareGuide(slug: LifeCompareSlug): { href: string; guide: BuyingGuide } | undefined {
  const guide = getBuyingGuide(slug);
  return guide ? { href: `/compare/${guide.slug}`, guide } : undefined;
}

/** 「公式ページに記載なし」は表に出さない（比較表のセルは空欄、注意点の箇条書きは項目ごと消す。lib/no-data.ts） */
function withoutNoDataGuide(guide: BuyingGuide): BuyingGuide {
  return {
    ...guide,
    products: (guide.products ?? []).map((product) => ({
      ...product,
      specs: product.specs?.map(withoutNoData),
      limits: withoutNoDataList(product.limits),
      cells: product.cells && Object.fromEntries(Object.entries(product.cells).map(([k, v]) => [k, withoutNoData(v)])),
    })),
  };
}

export function getAllBuyingGuides(): BuyingGuide[] {
  // 開発中は生成スクリプトが書き足したガイドをすぐ見られるよう、毎回読み直す
  if (cache && process.env.NODE_ENV === "production") return cache;
  if (!fs.existsSync(DIR)) return (cache = []);
  cache = fs
    .readdirSync(DIR)
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) => {
      try {
        // 文末の「〜しましょう」は落ち着いた言い方にして出す（台帳 W13。lib/polite-text.ts）
        return [politeDeep(withoutNoDataGuide(JSON.parse(fs.readFileSync(path.join(DIR, file), "utf8")) as BuyingGuide))];
      } catch {
        return [];
      }
    })
    .filter((guide) => resolveProducts(guide).length >= 2)
    .sort((a, b) => a.title.localeCompare(b.title, "ja"));
  return cache;
}

export function getBuyingGuide(slug: string): BuyingGuide | undefined {
  return getAllBuyingGuides().find((guide) => guide.slug === slug);
}

/**
 * 表示する商品（リンク・画像つき）。
 * 提携商品は提携が切れたら自動で消える。提携していない商品（name と officialUrl がある）は公式サイトへ案内する。
 */
export function resolveProducts(guide: BuyingGuide): ResolvedProduct[] {
  return guide.products.flatMap((product): ResolvedProduct[] => {
    const priceText = product.price || "公式サイトで確認";
    if (product.partner) {
      const found = partnerItem(product.partner);
      if (!found) return [];
      // 静的な比較ページは期限を迎えた時点で再生成される保証がないため、期限つきの販売は載せない。
      if (found.item.activeUntil) return [];
      const item = { ...found.item, price: null, priceText };
      return [{ ...product, key: product.id ?? product.partner, item, pixel: found.pixel, sponsored: true }];
    }
    if (!product.id || !product.name || !product.officialUrl) return [];
    const item: OfferItem = {
      key: product.id,
      kind: "partner",
      name: product.name,
      badge: product.category,
      image: null,
      price: null,
      priceText,
      url: product.officialUrl,
      shop: product.maker ?? product.name,
      cta: "公式サイトで見る",
    };
    return [{ ...product, key: product.id, item, sponsored: false }];
  });
}

/** 新形式（提携外の商品も並べ、判定・診断・詳しい比較表を持つ）か */
export function isRichGuide(guide: BuyingGuide): boolean {
  return (guide.schemaVersion ?? 1) >= 2;
}

export function guideRelatedArticles(guide: BuyingGuide, limit = 6): ArticleSummary[] {
  return guide.relatedArticleSlugs.flatMap((slug) => getArticleSummary(slug) ?? []).slice(0, limit);
}

/** 記事の商品枠の話題（offers.json のキー）に対応する比較ガイド */
export function buyingGuideForTopic(topic: string | undefined): BuyingGuide | undefined {
  if (!COMPARE_PUBLIC) return undefined;
  if (!topic) return undefined;
  return getAllBuyingGuides().find((guide) => guide.topics.includes(topic));
}

/** ガイドの見出しから「〇〇を選ぶなら」に使う短い名前（【】や：以降を落とす） */
export function guideShortName(guide: BuyingGuide): string {
  if (guide.shortName) return guide.shortName;
  return guide.title.split(/[【：:]/)[0].replace(/(おすすめ)?比較$/, "").replace(/おすすめ$/, "").trim();
}
