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
 * 総務省の計算式で「自己負担2,000円で済む寄附額の目安」を出す（式は lib/calc-math.ts）。
 * 2026-11-11: 通知書を持っていない人が多いため、年収と家族構成からの「かんたん」を既定にした（lib/furusato-easy.ts）。
 * 総務省が2025年10月まで載せていた目安表と同じ前提で計算し、表の年収300万〜900万円と一致することを tests/test_furusato_easy.cjs で確かめている。
 * 2026-11-25: 児童手当の支給額（/tools/child-allowance）を追加。子どもの生まれた年月か年齢の区分から、第何子・月額・12月の支給（10月・11月分）・1年分を
 * こども家庭庁の案内（令和6年10月分からの制度）で出す（式は lib/child-allowance.ts、テストは tests/test_child_allowance.cjs）。
 * 2026-11-26: 年金生活者支援給付金（/tools/pension-support-benefit）を追加。老齢・障害・遺族の別、世帯の住民税、前年の収入、納めた月数から、
 * 対象かどうかの目安と令和8年度の月額・1回の支払い（2か月分）・1年分を日本年金機構の案内で出す（式は lib/pension-support-benefit.ts、テストは tests/test_pension_support_benefit.cjs）。
 * 2026-11-26: 冬の電気・ガス料金支援（/tools/denki-gas-discount）を追加。12月の電気・都市ガスの使用量（1月・2月は12月の1.2倍が初期値）から、
 * 2026年12月〜2027年2月使用分の月ごとの値引き額と3か月の合計を、資源エネルギー庁の特設サイトの単価で出す（式は lib/denki-gas-discount.ts、テストは tests/test_denki_gas_discount.cjs）。
 */
export type CalculatorKind = "defense-tax" | "furusato-limit" | "child-allowance" | "pension-support-benefit" | "denki-gas-discount";

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
    description: "年収と家族構成から、自己負担2,000円で済むふるさと納税の寄附額の目安を計算します。住民税決定通知書の所得割額からの計算もできます。",
    checked: "2026-11-11",
  },
  "child-allowance": {
    href: "/tools/child-allowance",
    title: "児童手当の支給額の計算",
    description: "子どもの生まれた年月か年齢の区分から、第何子になるか・1か月の児童手当・12月の支給額（10月・11月分）・1年分を計算します。所得制限はありません。",
    checked: "2026-11-25",
  },
  "pension-support-benefit": {
    href: "/tools/pension-support-benefit",
    title: "年金生活者支援給付金の計算",
    description: "老齢・障害・遺族の別と前年の収入、保険料を納めた月数から、年金生活者支援給付金の対象かどうかの目安と、令和8年度の月額・1回の支払い（2か月分）・1年分を計算します。",
    checked: "2026-11-26",
  },
  "denki-gas-discount": {
    href: "/tools/denki-gas-discount",
    title: "冬の電気代・ガス代の値引き額の計算",
    description: "12月の電気と都市ガスの使用量から、国の電気・ガス料金支援で2026年12月〜2027年2月使用分がいくら安くなるかを月ごとと3か月の合計で計算します。申請は不要です。",
    checked: "2026-11-26",
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
const CHILD_ALLOWANCE_WORDS = /児童手当/;
const PENSION_SUPPORT_WORDS = /年金生活者支援給付金/;
const DENKI_GAS_WORDS = /電気・ガス料金(の)?支援|電気・ガス(料金|代)の?(補助|値引き)|電気代.{0,30}(値引き|円引き|補助|支援)|ガス代.{0,30}(値引き|円引き|補助|支援)/;

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
  // 児童手当の記事（見出しに「児童手当」がある記事だけ。2026-11-25）
  if (CHILD_ALLOWANCE_WORDS.test(title)) {
    return { kind: "child-allowance", heading: /いくら|金額|支給額|月額|第3子|計算|振込|支給日/ };
  }
  // 年金生活者支援給付金の記事（見出しに「年金生活者支援給付金」がある記事だけ。2026-11-26）
  if (PENSION_SUPPORT_WORDS.test(title)) {
    return { kind: "pension-support-benefit", heading: /いくら|金額|給付額|月額|計算|対象|基準|所得/ };
  }
  // 冬の電気・ガス料金支援の記事（見出しに「電気・ガス料金支援」や「電気代…値引き」がある記事だけ。2026-11-26）
  if (DENKI_GAS_WORDS.test(title)) {
    return { kind: "denki-gas-discount", heading: /いくら|値引き|単価|金額|計算|安く|kWh/ };
  }
  return null;
}

/**
 * 手続きガイド（/guides/*）から案内する計算ツール。ふるさと納税のガイド（tool: "furusato"、または見出しに「ふるさと納税」「ワンストップ特例」）と、見出しに「児童手当」があるガイド。
 * ガイドには計算機そのものは置かず、ツールのページへの案内を1つ出す（components/HowtoGuideView.tsx）
 */
export function calculatorForGuide(guide: { tool?: string; title: string; seoTitle?: string }): CalculatorKind | null {
  if (guide.tool === "furusato" || /ふるさと納税|ワンストップ特例/.test(`${guide.title} ${guide.seoTitle ?? ""}`)) return "furusato-limit";
  // 児童手当のガイド（/guides/jidou-teate など）からは、児童手当の支給額の計算へ（2026-11-25）
  if (/児童手当/.test(`${guide.title} ${guide.seoTitle ?? ""}`)) return "child-allowance";
  // 年金生活者支援給付金のガイドからは、年金生活者支援給付金の計算へ（2026-11-26）
  if (PENSION_SUPPORT_WORDS.test(`${guide.title} ${guide.seoTitle ?? ""}`)) return "pension-support-benefit";
  // 電気・ガス料金支援のガイドからは、冬の電気代・ガス代の値引き額の計算へ（2026-11-26）
  if (DENKI_GAS_WORDS.test(`${guide.title} ${guide.seoTitle ?? ""}`)) return "denki-gas-discount";
  return null;
}
