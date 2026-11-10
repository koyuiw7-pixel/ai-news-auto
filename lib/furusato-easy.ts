/**
 * ふるさと納税の上限額の「かんたん計算」（年収と家族構成から）。サーバー・ブラウザ共通、依存なし。
 *
 * なぜ自前で計算するか（2026-11-11 確認）:
 *  総務省のふるさと納税ポータル「税金の控除について」は、2025年10月まで「全額控除されるふるさと納税額（年間上限）の目安」
 *  （給与収入×家族構成の表。社会保険料は給与収入の15%と仮定）を載せていたが、2026年2月までに表と計算シートを外した
 *  （表のPDF /main_content/000408217.pdf と計算シート 000408218.xlsx は 404）。そのため、総務省が使っていたのと同じ前提で、
 *  2026年（令和8年）の所得にかかる住民税（令和9年度分）のきまりで計算する。
 *  検算: 総務省が外す前の表（Web Archive 2025-10-23 の写し）の給与収入300万〜900万円の全セルと一致することを
 *  tests/test_furusato_easy.cjs で確かめている。
 *
 * 上限を決めるのは住民税の側だけ（地方税法 第37条の2 第11項）:
 *  特例分の上限 ＝ 調整控除後の所得割額 × 20%。特例分の割合は「課税総所得金額 − 人的控除差調整額」に当てはめた所得税の税率で決まる。
 *  上限の目安 ＝ 所得割額 × 20% ÷ 特例分の割合 ＋ 2,000円（lib/calc-math.ts の furusatoLimit と同じ式）。
 *  このため、所得税だけの基礎控除の引き上げ（令和8年度税制改正）は上限に入らない。
 *
 * 住民税（令和9年度分）の数字の出典:
 *  - 給与所得控除: 国税庁 タックスアンサー No.1410。令和8年度税制改正大綱（財務省）で最低保障額65万円→69万円、
 *    さらに令和9年度・10年度分の住民税は5万円の上乗せ（＝74万円）。年収220万円未満の人だけに効く。
 *  - 基礎控除43万円（合計所得2,400万円以下）、配偶者控除33万円、扶養控除（一般）33万円・（特定 19〜22歳）45万円、
 *    人的控除差調整額（基礎5万円・配偶者5万円・一般扶養5万円・特定扶養18万円）、調整控除5%: 地方税法 第34条・第37条。
 *  - 所得金額調整控除（年収850万円超で23歳未満の扶養親族がいる人）: 国税庁 タックスアンサー No.1411。
 */

export type FurusatoFamily = {
  /** 配偶者控除を受けるか（配偶者の収入なし＝「夫婦」。共働きは false） */
  spouse: boolean;
  /** 16〜18歳の扶養親族（高校生など）の人数 */
  teens: number;
  /** 19〜22歳の扶養親族（大学生など）の人数 */
  students: number;
};

export type FurusatoEasyInput = FurusatoFamily & {
  /** 給与の年収（額面・税込み） */
  salary: number;
  /** 社会保険料の年額。省略すると給与収入の15%（総務省の目安表と同じ仮定） */
  socialInsurance?: number;
  /** iDeCo・小規模企業共済などの掛金の年額 */
  ideco?: number;
  /** 生命保険料控除・医療費控除など、ほかの所得控除の住民税での合計 */
  otherDeductions?: number;
};

export type FurusatoEasyResult = {
  /** 自己負担2,000円で済む寄附額の目安（1円未満切り捨て） */
  limit: number;
  /** 1,000円未満を切り捨てた額（総務省の表と同じ丸め） */
  rounded: number;
  /** 計算に使った住民税の所得割額（調整控除後） */
  levy: number;
  /** 住民税の課税所得（1,000円未満切り捨て） */
  taxable: number;
  /** 特例分の計算に使った所得税の税率（%） */
  rate: number;
  /** 社会保険料（仮定または入力） */
  socialInsurance: number;
};

const floorTo = (value: number, unit: number) => Math.floor(value / unit) * unit;

/** 給与所得（2026年分。年収660万円未満は所得税法 別表第五の4,000円刻みと同じ扱い） */
export function salaryIncome(salary: number): number {
  const s = Math.max(0, Math.floor(salary));
  if (s < 6_600_000) {
    // 最低保障 74万円（69万円＋特例5万円）の範囲。30%＋8万円 が 74万円を超えるのは年収220万円から
    if (s < 2_200_000) return Math.max(0, s - 740_000);
    const a = floorTo(s, 4000);
    if (a < 3_600_000) return Math.floor((a * 70) / 100) - 80_000;
    return Math.floor((a * 80) / 100) - 440_000;
  }
  if (s < 8_500_000) return Math.floor((s * 90) / 100) - 1_100_000;
  return s - 1_950_000;
}

/** 特例分の割合（10万分率）を決める税率。lib/calc-math.ts の FURUSATO_TAX_RATES と同じ段 */
function specialRate(base: number): number {
  if (base < 0) return 0;
  if (base <= 1_950_000) return 5;
  if (base <= 3_300_000) return 10;
  if (base <= 6_950_000) return 20;
  if (base <= 9_000_000) return 23;
  if (base <= 18_000_000) return 33;
  if (base <= 40_000_000) return 40;
  return 45;
}

export function furusatoEasy(input: FurusatoEasyInput): FurusatoEasyResult | null {
  const salary = Math.floor(input.salary);
  if (!(salary > 0)) return null;
  const teens = Math.max(0, Math.floor(input.teens));
  const students = Math.max(0, Math.floor(input.students));
  const social = input.socialInsurance !== undefined && input.socialInsurance >= 0 ? Math.floor(input.socialInsurance) : Math.floor((salary * 15) / 100);
  const ideco = Math.max(0, Math.floor(input.ideco ?? 0));
  const other = Math.max(0, Math.floor(input.otherDeductions ?? 0));

  // 所得金額調整控除（年収850万円超で、23歳未満の扶養親族がいる人）
  const adjust = salary > 8_500_000 && teens + students > 0 ? Math.floor((Math.min(salary, 10_000_000) - 8_500_000) / 10) : 0;
  const income = Math.max(0, salaryIncome(salary) - adjust);

  const basic = income <= 24_000_000 ? 430_000 : income <= 24_500_000 ? 290_000 : income <= 25_000_000 ? 150_000 : 0;
  const spouse = !input.spouse ? 0 : income <= 9_000_000 ? 330_000 : income <= 9_500_000 ? 220_000 : income <= 10_000_000 ? 110_000 : 0;
  const personal = basic + spouse + teens * 330_000 + students * 450_000;
  const taxable = floorTo(Math.max(0, income - social - ideco - other - personal), 1000);

  // 人的控除差調整額（調整控除と特例分の割合に使う）
  const spouseDiff = !input.spouse ? 0 : income <= 9_000_000 ? 50_000 : income <= 9_500_000 ? 40_000 : income <= 10_000_000 ? 20_000 : 0;
  const diff = (income <= 25_000_000 ? 50_000 : 0) + spouseDiff + teens * 50_000 + students * 180_000;

  // 調整控除（合計所得2,500万円以下）。市町村民税3%・道府県民税2%
  let adjBase = 0;
  if (income <= 25_000_000 && taxable > 0) {
    adjBase = taxable <= 2_000_000 ? Math.min(diff, taxable) : Math.max(diff - (taxable - 2_000_000), 50_000);
  }
  const city = Math.max(0, floorTo((taxable * 6) / 100 - (adjBase * 3) / 100, 100));
  const pref = Math.max(0, floorTo((taxable * 4) / 100 - (adjBase * 2) / 100, 100));
  const levy = city + pref;
  if (!(levy > 0)) return { limit: 0, rounded: 0, levy: 0, taxable, rate: 0, socialInsurance: social };

  const rate = specialRate(taxable - diff);
  const share = 90000 - rate * 1021;
  const limit = Math.floor((levy * 20000) / share) + 2000;
  return { limit, rounded: floorTo(limit, 1000), levy, taxable, rate, socialInsurance: social };
}

/** 総務省の目安表の家族構成（列の順）。かんたん計算の選択肢にも使う */
export const FURUSATO_FAMILIES = [
  { key: "single", label: "独身・共働き（子どもなし）", short: "独身・共働き", family: { spouse: false, teens: 0, students: 0 } },
  { key: "couple", label: "夫婦（配偶者の収入なし）", short: "夫婦", family: { spouse: true, teens: 0, students: 0 } },
  { key: "dual-teen", label: "共働き＋高校生1人", short: "共働き＋高校生", family: { spouse: false, teens: 1, students: 0 } },
  { key: "dual-student", label: "共働き＋大学生1人", short: "共働き＋大学生", family: { spouse: false, teens: 0, students: 1 } },
  { key: "couple-teen", label: "夫婦＋高校生1人", short: "夫婦＋高校生", family: { spouse: true, teens: 1, students: 0 } },
  { key: "dual-both", label: "共働き＋大学生と高校生", short: "共働き＋大学生・高校生", family: { spouse: false, teens: 1, students: 1 } },
  { key: "couple-both", label: "夫婦＋大学生と高校生", short: "夫婦＋大学生・高校生", family: { spouse: true, teens: 1, students: 1 } },
] as const satisfies readonly { key: string; label: string; short: string; family: FurusatoFamily }[];

/**
 * 所得税（基準所得税額・復興特別所得税を含まない）の目安。2026年分・2027年分のきまり（2026-11-11 確認）。
 *  - 基礎控除: 国税庁 タックスアンサー No.1199（令和8年分・令和9年分: 合計所得489万円以下104万円、655万円以下67万円、
 *    2,350万円以下62万円、2,400万円以下48万円、2,450万円以下32万円、2,500万円以下16万円）
 *  - 給与所得控除: No.1410（令和8年分・令和9年分の最低74万円）。所得金額調整控除: No.1411
 *  - 配偶者控除38万円・扶養控除（一般38万円・特定63万円）: No.1191・No.1180。税率: No.2260 の速算表
 * 住宅ローン控除などの税額控除を引く前の額。ふるさと納税の住宅ローン控除の確認と、防衛特別所得税の「年収から」の目安に使う。
 */
export function incomeTaxEstimate(input: FurusatoEasyInput): number {
  const salary = Math.floor(input.salary);
  if (!(salary > 0)) return 0;
  const teens = Math.max(0, Math.floor(input.teens));
  const students = Math.max(0, Math.floor(input.students));
  const social = input.socialInsurance !== undefined && input.socialInsurance >= 0 ? Math.floor(input.socialInsurance) : Math.floor((salary * 15) / 100);
  const ideco = Math.max(0, Math.floor(input.ideco ?? 0));
  const other = Math.max(0, Math.floor(input.otherDeductions ?? 0));
  const adjust = salary > 8_500_000 && teens + students > 0 ? Math.floor((Math.min(salary, 10_000_000) - 8_500_000) / 10) : 0;
  const income = Math.max(0, salaryIncome(salary) - adjust);
  const basic =
    income <= 4_890_000 ? 1_040_000 : income <= 6_550_000 ? 670_000 : income <= 23_500_000 ? 620_000 : income <= 24_000_000 ? 480_000 : income <= 24_500_000 ? 320_000 : income <= 25_000_000 ? 160_000 : 0;
  const spouse = !input.spouse ? 0 : income <= 9_000_000 ? 380_000 : income <= 9_500_000 ? 260_000 : income <= 10_000_000 ? 130_000 : 0;
  const taxable = floorTo(Math.max(0, income - social - ideco - other - basic - spouse - teens * 380_000 - students * 630_000), 1000);
  const brackets: [number, number, number][] = [
    [1_949_000, 5, 0],
    [3_299_000, 10, 97_500],
    [6_949_000, 20, 427_500],
    [8_999_000, 23, 636_000],
    [17_999_000, 33, 1_536_000],
    [39_999_000, 40, 2_796_000],
    [Infinity, 45, 4_796_000],
  ];
  const [, rate, minus] = brackets.find(([max]) => taxable <= max)!;
  return Math.max(0, Math.floor((taxable * rate) / 100) - minus);
}

/** 61,000 → "6.1"（1,000円未満を切り捨てた額を万円で。結果の大きな数字に使う） */
export function furusatoManYen(rounded: number): string {
  return (Math.floor(rounded / 1000) / 10).toLocaleString("ja-JP", { maximumFractionDigits: 1 });
}

/** ページの「年収と家族構成別の目安」の表（ビルドのときに furusatoEasy で計算する。手で書かない） */
export const FURUSATO_EASY_SALARIES = [3_000_000, 4_000_000, 5_000_000, 6_000_000, 7_000_000, 8_000_000, 9_000_000, 10_000_000, 12_000_000, 15_000_000] as const;
export const FURUSATO_EASY_TABLE_FAMILIES = ["single", "couple", "couple-teen", "couple-both"] as const;

export function furusatoEasyTable(): { salary: number; cells: { key: string; rounded: number | null }[] }[] {
  return FURUSATO_EASY_SALARIES.map((salary) => ({
    salary,
    cells: FURUSATO_EASY_TABLE_FAMILIES.map((key) => {
      const family = FURUSATO_FAMILIES.find((f) => f.key === key)!.family;
      const r = furusatoEasy({ salary, ...family });
      return { key, rounded: r && r.rounded >= 3000 ? r.rounded : null };
    }),
  }));
}
