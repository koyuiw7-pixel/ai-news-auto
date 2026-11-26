/**
 * 冬のボーナス（賞与）の手取りの計算（/tools/bonus-tedori と、見出しに「ボーナス」「賞与」がある記事の中の計算機）。サーバー・ブラウザ共通、依存なし。
 * 式は tests/test_bonus_tedori.cjs で確かめている。2026-11-26 に公式資料で確認。
 *
 * 出典:
 *  - 協会けんぽ「令和8年度の協会けんぽの保険料率は3月分（4月納付分）から改定されます」
 *    （https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/rate_prefectures/r08/index.html）
 *    都道府県ごとの健康保険料率（令和8年3月分から）。47都道府県すべて、同じページの表と
 *    「令和8年度保険料額表 エクセル版（全都道府県分）」（https://www.kyoukaikenpo.or.jp/assets/r8ippan3.xlsx）の
 *    「介護保険第2号被保険者に該当する場合」の率（健康保険料率＋1.62%）が一致することを確かめた。
 *  - 協会けんぽ「協会けんぽの介護保険料率について」（https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/002/index.html）
 *    令和8年3月分から 1.62%（40歳から64歳までの人）。
 *  - 協会けんぽ「協会けんぽの子ども・子育て支援金率について」（https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/003/index.html）
 *    令和8年4月分（5月納付分）から 0.23%。
 *  - 協会けんぽ 東京支部「令和8年3月分（4月納付分）からの健康保険・厚生年金保険の保険料額表」（https://www.kyoukaikenpo.or.jp/assets/R8_13tokyo.pdf）
 *    賞与の保険料＝標準賞与額（賞与額の1,000円未満を切り捨て）×保険料率。標準賞与額の上限は、健康保険・介護保険・子ども・子育て支援金が
 *    年度（4月〜翌年3月）の累計573万円、厚生年金保険が1か月150万円。厚生年金保険料率18.300%。
 *    給与から引く本人負担分の端数は、50銭以下を切り捨て、50銭を超えると切り上げて1円（特約があればそれによる）。
 *  - 厚生労働省「令和８（2026）年度 雇用保険料率のご案内」（https://www.mhlw.go.jp/content/001692566.pdf）
 *    令和8年4月1日〜令和9年3月31日、一般の事業の労働者負担は 5/1,000（令和7年度は5.5/1,000）。
 *  - 厚生労働省「雇用保険被保険者からの雇用保険料の控除方法」（https://www.mhlw.go.jp/new-info/kobetu/roudou/gyousei/hoken/2020/dl/keizoku-20.pdf）
 *    本人負担分＝賃金総額×率。給与から引くときの端数は50銭以下切り捨て、50銭1厘以上切り上げ。
 *  - 国税庁「賞与に対する源泉徴収税額の算出率の表（令和8年分）」（https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2026/data/15-16.pdf）
 *    甲欄（扶養控除等申告書を出している人）。率は所得税と復興特別所得税を合わせたもの。
 *    表によらず月額表で計算する場合（前月の給与が無い・賞与が前月の給与の10倍を超える）は、この計算機では出さない。
 *  - 国税庁「令和8年分 源泉徴収税額表」の使い方（https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2026/data/19-22.pdf）
 *    税額＝（賞与−社会保険料等）×率、1円未満の端数は切り捨て。設例（賞与554,000円・社会保険料85,593円・前月196,616円・扶養2人 → 9,564円）。
 *
 * 書かないこと（公式資料で確かめていないため）: 健康保険組合ごとの料率（読者が入れる）、乙欄・丙欄、月額表を使う場合の税額、
 * 70歳以上・75歳以上の扱い、建設・農林水産の事業の雇用保険料率の計算（文中で率だけ案内）。
 */

export const BONUS_SOURCES = {
  ntaRate: { href: "https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2026/data/15-16.pdf", label: "国税庁「賞与に対する源泉徴収税額の算出率の表（令和8年分）」" },
  ntaHow: { href: "https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2026/data/19-22.pdf", label: "国税庁「令和8年分 源泉徴収税額表」の使い方と設例" },
  kyokaiRate: { href: "https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/rate_prefectures/r08/index.html", label: "協会けんぽ「令和8年度の都道府県単位保険料率」" },
  kyokaiTable: { href: "https://www.kyoukaikenpo.or.jp/assets/R8_13tokyo.pdf", label: "協会けんぽ「令和8年3月分からの保険料額表（東京支部）」" },
  kyokaiKaigo: { href: "https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/002/index.html", label: "協会けんぽ「介護保険料率について」" },
  kyokaiShien: { href: "https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/003/index.html", label: "協会けんぽ「子ども・子育て支援金率について」" },
  mhlwKoyo: { href: "https://www.mhlw.go.jp/content/001692566.pdf", label: "厚生労働省「令和8（2026）年度 雇用保険料率のご案内」" },
  mhlwKoyoRound: { href: "https://www.mhlw.go.jp/new-info/kobetu/roudou/gyousei/hoken/2020/dl/keizoku-20.pdf", label: "厚生労働省「雇用保険被保険者からの雇用保険料の控除方法」" },
} as const;

/** 協会けんぽの都道府県ごとの健康保険料率（%、会社と本人の合計。令和8年3月分から） */
export const KYOKAI_HEALTH_RATES: readonly (readonly [string, number])[] = [
  ["北海道", 10.28], ["青森県", 9.85], ["岩手県", 9.51], ["宮城県", 10.1], ["秋田県", 10.01], ["山形県", 9.75], ["福島県", 9.5],
  ["茨城県", 9.52], ["栃木県", 9.82], ["群馬県", 9.68], ["埼玉県", 9.67], ["千葉県", 9.73], ["東京都", 9.85], ["神奈川県", 9.92],
  ["新潟県", 9.21], ["富山県", 9.59], ["石川県", 9.7], ["福井県", 9.71], ["山梨県", 9.55], ["長野県", 9.63],
  ["岐阜県", 9.8], ["静岡県", 9.61], ["愛知県", 9.93], ["三重県", 9.77],
  ["滋賀県", 9.88], ["京都府", 9.89], ["大阪府", 10.13], ["兵庫県", 10.12], ["奈良県", 9.91], ["和歌山県", 10.06],
  ["鳥取県", 9.86], ["島根県", 9.94], ["岡山県", 10.05], ["広島県", 9.78], ["山口県", 10.15],
  ["徳島県", 10.24], ["香川県", 10.02], ["愛媛県", 9.98], ["高知県", 10.05],
  ["福岡県", 10.11], ["佐賀県", 10.55], ["長崎県", 10.06], ["熊本県", 10.08], ["大分県", 10.08], ["宮崎県", 9.77], ["鹿児島県", 10.13], ["沖縄県", 9.44],
];

/** 介護保険料率（%、合計。40歳から64歳までの人。令和8年3月分から） */
export const KYOKAI_KAIGO_RATE = 1.62;
/** 子ども・子育て支援金率（%、合計。令和8年4月分から） */
export const KYOKAI_SHIEN_RATE = 0.23;
/** 厚生年金保険料率（%、合計） */
export const KOSEI_NENKIN_RATE = 18.3;
/** 雇用保険料率（本人負担、一般の事業。令和8年4月〜令和9年3月）＝ 5/1,000 */
export const KOYO_RATE_PER_MILLE = 5;
/** 標準賞与額の上限（厚生年金は1か月150万円。健康保険・介護・支援金は年度の累計573万円） */
export const KOSEI_NENKIN_BONUS_CAP = 1_500_000;
export const HEALTH_BONUS_YEARLY_CAP = 5_730_000;

/** 算出率の表の「賞与の金額に乗ずべき率」（%。所得税と復興特別所得税を合わせた率） */
export const BONUS_TAX_RATES: readonly number[] = [
  0, 2.042, 4.084, 6.126, 8.168, 10.21, 12.252, 14.294, 16.336, 18.378, 20.42, 22.462, 24.504, 26.546, 28.588, 30.63, 32.672, 35.735, 38.798, 41.861, 45.945,
];

/**
 * 甲欄。扶養親族等の数（0人〜7人以上）ごとに、2行目（2.042%）から最後の行（45.945%）までの「以上」の額（千円）。
 * ある行の「未満」は次の行の「以上」。いちばん上の行（0.000%）は最初の額の未満
 */
export const BONUS_TAX_KOU: readonly (readonly number[])[] = [
  [82, 94, 260, 309, 342, 372, 402, 433, 520, 605, 684, 715, 752, 795, 854, 922, 1318, 1521, 2621, 3495],
  [107, 250, 289, 346, 373, 401, 430, 463, 520, 621, 705, 739, 778, 821, 882, 952, 1342, 1526, 2645, 3527],
  [143, 276, 321, 377, 400, 426, 457, 492, 525, 636, 728, 764, 804, 848, 910, 983, 1367, 1526, 2669, 3559],
  [181, 300, 354, 405, 424, 452, 484, 517, 550, 651, 751, 788, 830, 876, 938, 1013, 1391, 1538, 2693, 3590],
  [218, 300, 387, 431, 452, 477, 509, 540, 577, 666, 774, 813, 856, 903, 966, 1044, 1416, 1555, 2716, 3622],
  [251, 304, 412, 457, 479, 503, 531, 564, 604, 681, 798, 838, 881, 930, 994, 1074, 1440, 1555, 2740, 3654],
  [284, 343, 438, 483, 505, 527, 553, 589, 630, 697, 821, 862, 907, 957, 1022, 1104, 1464, 1555, 2764, 3685],
  [317, 383, 463, 508, 529, 552, 578, 614, 657, 708, 845, 887, 933, 985, 1051, 1135, 1489, 1583, 2788, 3717],
];

/** 前月の給与（社会保険料等を引いた後）と扶養親族等の数から、賞与に掛ける率（%） */
export function bonusTaxRate(prevNet: number, dependents: number): number {
  const column = BONUS_TAX_KOU[Math.min(7, Math.max(0, Math.floor(dependents)))];
  let row = 0;
  for (let i = 0; i < column.length; i++) if (prevNet >= column[i] * 1000) row = i + 1;
  return BONUS_TAX_RATES[row];
}

/** 率の行の「以上」「未満」（円）。いちばん上の行は from が 0、いちばん下の行は to が undefined */
export function bonusTaxBand(prevNet: number, dependents: number): { from: number; to?: number } {
  const column = BONUS_TAX_KOU[Math.min(7, Math.max(0, Math.floor(dependents)))];
  let row = 0;
  for (let i = 0; i < column.length; i++) if (prevNet >= column[i] * 1000) row = i + 1;
  return { from: row === 0 ? 0 : column[row - 1] * 1000, to: row < column.length ? column[row] * 1000 : undefined };
}

/** 給与から引く本人負担分の端数：50銭以下は切り捨て、50銭を超えると切り上げ（協会けんぽの保険料額表・厚生労働省の雇用保険料の案内） */
export function roundShare(value: number): number {
  // 浮動小数の誤差（24,625.000000001 など）を避けるため、銭（1/100円）の単位にそろえてから比べる
  const sen = Math.round(value * 100);
  const yen = Math.floor(sen / 100);
  return sen - yen * 100 > 50 ? yen + 1 : yen;
}

/** 標準賞与額（1,000円未満を切り捨て） */
export function standardBonus(bonus: number): number {
  return Math.floor(bonus / 1000) * 1000;
}

export function prefectureRate(prefecture: string): number | undefined {
  return KYOKAI_HEALTH_RATES.find(([name]) => name === prefecture)?.[1];
}

export type BonusInput = {
  /** 賞与の額面（円） */
  bonus: number;
  /** 前月の給与から社会保険料を引いた額（円） */
  prevNet: number;
  /** 扶養親族等の数 */
  dependents: number;
  /** 40歳から64歳まで（介護保険料がかかる） */
  kaigo: boolean;
  /** 協会けんぽの都道府県（insurer が "kyokai" のとき） */
  prefecture?: string;
  /** 健康保険組合のとき、本人が負担する率（%）。kyokai のときは使わない */
  insurer?: "kyokai" | "kumiai";
  kumiaiHealth?: number;
  kumiaiKaigo?: number;
  kumiaiShien?: number;
};

export type BonusResult = {
  standard: number;
  /** 厚生年金の標準賞与額（150万円が上限） */
  pensionStandard: number;
  health: number;
  kaigo: number;
  shien: number;
  pension: number;
  koyo: number;
  social: number;
  /** 所得税（復興特別所得税を含む）。算出率の表では出せないときは null */
  tax: number | null;
  taxRate: number | null;
  /** 算出率の表を使えない理由（前月の給与が無い・賞与が前月の10倍を超える） */
  taxNote?: "no-prev" | "over-10x";
  /** 手取り（所得税が出せないときは、社会保険料だけを引いた額） */
  takeHome: number;
  /** 使った本人負担の率（%） */
  rates: { health: number; kaigo: number; shien: number; pension: number; koyo: number };
};

export function bonusTedori(input: BonusInput): BonusResult {
  const bonus = Math.max(0, Math.floor(input.bonus));
  const standard = standardBonus(bonus);
  const pensionStandard = Math.min(standard, KOSEI_NENKIN_BONUS_CAP);
  const kumiai = input.insurer === "kumiai";
  const healthRate = kumiai ? (input.kumiaiHealth ?? 0) : (prefectureRate(input.prefecture ?? "東京都") ?? 0) / 2;
  const kaigoRate = input.kaigo ? (kumiai ? (input.kumiaiKaigo ?? 0) : KYOKAI_KAIGO_RATE / 2) : 0;
  const shienRate = kumiai ? (input.kumiaiShien ?? 0) : KYOKAI_SHIEN_RATE / 2;
  const pensionRate = KOSEI_NENKIN_RATE / 2;
  const koyoRate = KOYO_RATE_PER_MILLE / 10;
  const health = roundShare((standard * healthRate) / 100);
  const kaigo = roundShare((standard * kaigoRate) / 100);
  const shien = roundShare((standard * shienRate) / 100);
  const pension = roundShare((pensionStandard * pensionRate) / 100);
  const koyo = roundShare((bonus * KOYO_RATE_PER_MILLE) / 1000);
  const social = health + kaigo + shien + pension + koyo;
  const afterSocial = Math.max(0, bonus - social);
  const prevNet = Math.max(0, Math.floor(input.prevNet));
  let tax: number | null = null;
  let taxRate: number | null = null;
  let taxNote: BonusResult["taxNote"];
  if (prevNet <= 0) taxNote = "no-prev";
  else if (afterSocial > prevNet * 10) taxNote = "over-10x";
  else {
    taxRate = bonusTaxRate(prevNet, input.dependents);
    // 率は小数3桁の%。1,000倍した整数で掛けて、浮動小数の誤差を避ける
    tax = Math.floor((afterSocial * Math.round(taxRate * 1000)) / 100_000);
  }
  return {
    standard,
    pensionStandard,
    health,
    kaigo,
    shien,
    pension,
    koyo,
    social,
    tax,
    taxRate,
    taxNote,
    takeHome: afterSocial - (tax ?? 0),
    rates: { health: healthRate, kaigo: kaigoRate, shien: shienRate, pension: pensionRate, koyo: koyoRate },
  };
}

/** ページの「計算の例」と、計算機の最初の値（賞与50万円・前月の給与30万円・扶養0人・東京都・40歳未満・協会けんぽ） */
export const BONUS_EXAMPLE: BonusInput = { bonus: 500_000, prevNet: 300_000, dependents: 0, kaigo: false, prefecture: "東京都", insurer: "kyokai" };

/** 例の表：賞与の額ごとの手取り（前月の給与30万円・扶養0人・東京都・40歳未満） */
export const BONUS_EXAMPLE_AMOUNTS = [300_000, 500_000, 700_000, 1_000_000] as const;

export function bonusExampleTable(): { bonus: number; result: BonusResult }[] {
  return BONUS_EXAMPLE_AMOUNTS.map((bonus) => ({ bonus, result: bonusTedori({ ...BONUS_EXAMPLE, bonus }) }));
}

export function yenJa(value: number): string {
  return `${Math.round(value).toLocaleString("ja-JP")}円`;
}

/** 本人負担の率の表示（例：4.925%） */
export function percentJa(value: number): string {
  return `${Number(value.toFixed(4)).toString()}%`;
}
