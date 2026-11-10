/**
 * 計算機（/tools/defense-tax・/tools/furusato-limit）と記事の図で使う計算。サーバー・ブラウザ共通、依存なし。
 * ここの式は tests/test_charts_calc.cjs で確かめている。
 */

/**
 * 防衛特別所得税・復興特別所得税（国の税）の税率。
 * 出典: 財務省「令和8年度税制改正の大綱」（防衛特別所得税＝基準所得税額×1%、令和9年＝2027年分から当分の間。
 * 復興特別所得税は2027年分から1.1%に下げ、課税期間を2047年まで延長）。国税庁「令和9年分 源泉徴収税額表」。
 */
export function surtaxRates(year: number): { defense: number; reconstruction: number } {
  if (year < 2013) return { defense: 0, reconstruction: 0 };
  if (year <= 2026) return { defense: 0, reconstruction: 0.021 };
  if (year <= 2047) return { defense: 0.01, reconstruction: 0.011 };
  return { defense: 0.01, reconstruction: 0 };
}

/** 改正前のきまり（復興特別所得税 2.1% を 2037年まで）。改正でどう変わったかを並べるため */
export function surtaxRatesBeforeReform(year: number): { defense: number; reconstruction: number } {
  if (year < 2013 || year > 2037) return { defense: 0, reconstruction: 0 };
  return { defense: 0, reconstruction: 0.021 };
}

export type Surtax = { defense: number; reconstruction: number; total: number };

/** 基準所得税額から、その年の防衛特別所得税と復興特別所得税（それぞれ1円未満切り捨て） */
export function surtax(baseIncomeTax: number, year: number, beforeReform = false): Surtax {
  const base = Math.max(0, Math.floor(baseIncomeTax));
  const rates = beforeReform ? surtaxRatesBeforeReform(year) : surtaxRates(year);
  const defense = Math.floor(base * rates.defense);
  const reconstruction = Math.floor(base * rates.reconstruction);
  return { defense, reconstruction, total: defense + reconstruction };
}

/**
 * 源泉徴収票の「源泉徴収税額」（所得税と復興特別所得税などの合計。2026年分までも2027年分からも合計の率は 2.1%）から、
 * 基準所得税額（所得税だけ）の目安。年末調整で100円未満を切り捨てているので、数十円ずれることがある。
 */
export function baseFromWithheld(withheld: number): number {
  if (!(withheld > 0)) return 0;
  return Math.floor(withheld / 1.021);
}

/**
 * ふるさと納税で、自己負担が2,000円で済む寄附額の上限の目安（2026年＝令和8年の寄附）。2026-11-10 に公式ページで確認。
 *
 * 出典:
 *  - 総務省 ふるさと納税ポータル「税金の控除について」: 住民税からの控除（特例分）＝（寄附額−2,000円）×（100%−10%−所得税の税率）。
 *    特例分が住民税所得割額の2割を超えると、特例分＝住民税所得割額×20% になり、自己負担は2,000円を超える。
 *    所得税の税率は復興特別所得税の税率を加えた率。
 *  - 国税庁 タックスアンサー No.1155（所得割額の20%を限度）・No.2260（所得税の税率と、復興特別所得税 2.1%）
 *  - 地方税法 第37条の2・第314条の7（特例控除額の上限は所得割の額の100分の20）、附則第5条の6
 *    （特例分の割合 84.895%・79.79%・69.58%・66.517%・56.307%・49.16%・44.055%。＝90%−所得税の税率×1.021）
 *
 * 上限の目安 ＝ 住民税の所得割額×20% ÷（90%−所得税の税率×1.021）＋ 2,000円
 * 総所得金額等の40%（所得税）・30%（住民税の基本分）の上限と、人ごとの控除の違いは入れていない（目安）。
 */
export const FURUSATO_TAX_RATES = [0, 5, 10, 20, 23, 33, 40, 45] as const;
export type FurusatoTaxRate = (typeof FURUSATO_TAX_RATES)[number];

/** 特例分の割合（10万分率）。5% → 84,895（84.895%）。小数の誤差を出さないよう整数で持つ */
export function furusatoSpecialShare(ratePercent: FurusatoTaxRate): number {
  return 90000 - ratePercent * 1021;
}

export type FurusatoLimit = {
  /** 特例分の上限（住民税の所得割額×20%。1円未満切り捨て） */
  cap: number;
  /** 自己負担が2,000円で済む寄附額の上限の目安（1円未満切り捨て） */
  limit: number;
  /** limit を1,000円未満で切り捨てた額（寄附額を決めるときの目安） */
  rounded: number;
};

export function furusatoLimit(residentIncomeLevy: number, ratePercent: FurusatoTaxRate): FurusatoLimit | null {
  if (!(residentIncomeLevy > 0) || !FURUSATO_TAX_RATES.includes(ratePercent)) return null;
  const levy = Math.floor(residentIncomeLevy);
  const share = furusatoSpecialShare(ratePercent);
  // （寄附額−2,000円）× share/100000 ≦ 所得割額×20% を満たす、いちばん大きい寄附額
  const limit = Math.floor((levy * 20000) / share) + 2000;
  return { cap: Math.floor(levy / 5), limit, rounded: Math.floor(limit / 1000) * 1000 };
}

/** 計算ページ（/tools/furusato-limit）の「計算の例」の表の行（住民税の所得割額）と列（所得税の税率） */
export const FURUSATO_EXAMPLE_LEVIES = [100000, 200000, 300000, 500000] as const;
export const FURUSATO_EXAMPLE_RATES = [5, 10, 20, 23] as const satisfies readonly FurusatoTaxRate[];
/** 「計算の例」の文章で使う1人分の例（所得割額300,000円・税率10% → 77,197円） */
export const FURUSATO_EXAMPLE = { levy: 300000, rate: 10 } as const satisfies { levy: number; rate: FurusatoTaxRate };

/** 「計算の例」の表。各セルは furusatoLimit() の limit（1円未満切り捨て） */
export function furusatoExampleTable(): { levy: number; cells: { rate: FurusatoTaxRate; limit: number }[] }[] {
  return FURUSATO_EXAMPLE_LEVIES.map((levy) => ({
    levy,
    cells: FURUSATO_EXAMPLE_RATES.map((rate) => ({ rate, limit: furusatoLimit(levy, rate)?.limit ?? 0 })),
  }));
}

/** 防衛特別所得税の計算機の最初の値（1年の基準所得税額）。ページの「計算の例」の文と同じ値を使う */
export const DEFENSE_TAX_DEFAULT_BASE = 150000;

/** 防衛特別所得税のページの「計算の例」の最初の文（1つの文字列で出し、HTMLの中で途切れないようにする） */
export function defenseTaxExampleSentence(base: number): string {
  return `例：1年の所得税額（基準所得税額）が${yen(base)}の場合`;
}

/** 防衛特別所得税の計算機と「計算の例」の年ごとの区切り（財務省「令和8年度税制改正の大綱」）。year はその区切りの代表の年 */
export const DEFENSE_TAX_PERIODS = [
  { label: "2026年分まで", year: 2026 },
  { label: "2027〜2037年分", year: 2030 },
  { label: "2038〜2047年分", year: 2040 },
  { label: "2048年分から", year: 2050 },
] as const;

/** 1,234,567 → "123.5万"、2.5e8 → "2.5億"（図の差分の表示用） */
export function compactJa(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const trim = (n: number) => (Math.round(n * 10) / 10).toLocaleString("ja-JP", { maximumFractionDigits: 1 });
  if (abs >= 1e12) return `${sign}${trim(abs / 1e12)}兆`;
  if (abs >= 1e8) return `${sign}${trim(abs / 1e8)}億`;
  if (abs >= 1e4) return `${sign}${trim(abs / 1e4)}万`;
  return `${sign}${abs.toLocaleString("ja-JP", { maximumFractionDigits: 2 })}`;
}

export function yen(value: number): string {
  return `${Math.round(value).toLocaleString("ja-JP")}円`;
}
