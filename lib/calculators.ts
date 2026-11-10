import type { ArticleChart } from "@/lib/charts";

/**
 * 記事に合う計算機（1記事に1つだけ）。本文の合う章の下に置き、無ければ本文の終わりに置く。
 * 計算機そのものは /tools/* の単独ページと同じ部品（components/calc）。
 */
/**
 * 2026-11-03 オーナー「このページもいらない」で /tools/usd-jpy（ドル建てサブスクの円換算）を終了した（台帳 W14。URL は cloudflare/worker.ts で 410）。
 * ドルの月額に為替と消費税を掛けるだけで、料金の段の表（円の目安つき）と重なり、記事への埋め込みも料金の話に合っていなかった。
 * 計算ツールは「公式の数字から読者自身の金額を出す」ものだけ置く（防衛特別所得税と、ふるさと納税の上限額）。
 * 2026-11-10: ふるさと納税の上限額（/tools/furusato-limit）を追加。住民税決定通知書の所得割額と所得税の税率から、
 * 総務省の計算式で「自己負担2,000円で済む寄附額の目安」を出す（年収からの推定はしない。式は lib/calc-math.ts）。
 */
export type CalculatorKind = "defense-tax" | "furusato-limit";

export type ArticleCalculator = {
  kind: CalculatorKind;
  /** この見出しの章の下に置く（無ければ本文の終わり） */
  heading: RegExp | null;
};

/**
 * checked は、そのページの出典（公式ページ）を開いて式・数字を確かめた日（YYYY-MM-DD）。ビルドの日ではない。
 * 出典を確かめ直したときだけ書き換える。JSON-LD の dateModified と、ページの「出典を確かめた日」に使う（2026-11-10 LLMO-A7）。
 */
export const CALCULATORS: Record<CalculatorKind, { href: string; title: string; description: string; checked: string }> = {
  "defense-tax": {
    href: "/tools/defense-tax",
    title: "防衛特別所得税の計算",
    description: "所得税額（基準所得税額）から、2027年からの防衛特別所得税と復興特別所得税を年ごとに計算します。",
    checked: "2026-11-03",
  },
  "furusato-limit": {
    href: "/tools/furusato-limit",
    title: "ふるさと納税の上限額の計算",
    description: "住民税の所得割額と所得税の税率から、自己負担2,000円で済むふるさと納税の寄附額の目安を、総務省の計算式で計算します。",
    checked: "2026-11-10",
  },
};

/** "2026-11-10" → "2026年11月10日" */
export function checkedDateJa(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return `${y}年${m}月${d}日`;
}

/** 計算機の単独ページの JSON-LD（WebApplication と パンくず）。dateModified は出典を確かめた日（checked） */
export function toolPageJsonLd(kind: CalculatorKind, site: { url: string; siteName: string }) {
  const meta = CALCULATORS[kind];
  const url = `${site.url}${meta.href}`;
  return [
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      name: meta.title,
      description: meta.description,
      url,
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      inLanguage: "ja",
      isAccessibleForFree: true,
      dateModified: meta.checked,
      offers: { "@type": "Offer", price: 0, priceCurrency: "JPY" },
      publisher: { "@type": "Organization", name: site.siteName, url: site.url },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "ホーム", item: site.url },
        { "@type": "ListItem", position: 2, name: meta.title, item: url },
      ],
    },
  ];
}

type ArticleLike = {
  title: string;
  seoTitle?: string;
  tags: string[];
  genreSlug?: string;
  body?: string;
  verdict?: { price?: string } | null;
  charts?: ArticleChart[];
};

const TAX_WORDS = /防衛特別所得税|防衛増税|防衛税|復興特別所得税/;
const FURUSATO_WORDS = /ふるさと納税/;

/**
 * AIの有料プランの費用計算（/tools/ai-plan-cost）は 2026-11-03 に終了した（「12か月で16,800円」「Plusの0.5個分」のような
 * 足し算・割り算だけで、読者に新しい情報が無かった。AdSense の「有用性の低いコンテンツ」対策。URL は cloudflare/worker.ts で 410）。
 * 料金の段の図がある記事は、図に円の目安が出ているので計算機を置かない。
 * 2つ目の引数は使っていない（呼び出し側の互換のため残している。呼び出し側から外したら消してよい）
 */
export function calculatorForArticle(article: ArticleLike): ArticleCalculator | null {
  const title = `${article.title} ${article.seoTitle ?? ""}`;
  // 税の記事（防衛特別所得税・復興特別所得税）
  if (TAX_WORDS.test(title) || article.tags.some((t) => TAX_WORDS.test(t))) {
    return { kind: "defense-tax", heading: /仕組み|いくら|負担|税率|数字|数値|変わる/ };
  }
  // ふるさと納税の記事（見出しに「ふるさと納税」がある記事だけ。タグや本文の脇の1語では置かない）
  if (FURUSATO_WORDS.test(title)) {
    return { kind: "furusato-limit", heading: /上限|限度|いくら|控除|計算|目安|仕組み/ };
  }
  return null;
}

/**
 * 手続きガイド（/guides/*）から案内する計算ツール。ふるさと納税のガイド（tool: "furusato"、または見出しに「ふるさと納税」「ワンストップ特例」）だけ。
 * ガイドには計算機そのものは置かず、ツールのページへの案内を1つ出す（components/HowtoGuideView.tsx）
 */
export function calculatorForGuide(guide: { tool?: string; title: string; seoTitle?: string }): CalculatorKind | null {
  if (guide.tool === "furusato" || /ふるさと納税|ワンストップ特例/.test(`${guide.title} ${guide.seoTitle ?? ""}`)) return "furusato-limit";
  return null;
}
