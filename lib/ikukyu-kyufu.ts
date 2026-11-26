/**
 * 育児休業給付金と出生後休業支援給付金の目安（/tools/ikukyu-kyufu と、見出しに「育児休業給付」「育休」がある記事の中の計算機）。サーバー・ブラウザ共通、依存なし。
 * 式は tests/test_ikukyu_kyufu.cjs で確かめている。2026-11-26 に公式資料を開いて確認。
 *
 * 出典:
 *  - 厚生労働省・都道府県労働局・ハローワーク「育児休業等給付の内容と支給申請手続」2026（令和8）年8月1日改訂版
 *    （https://www.mhlw.go.jp/content/11600000/001461102.pdf）
 *    育児休業給付金の支給額＝休業開始時賃金日額×支給日数×67%（育児休業開始から181日目以降は50%）。支給日数は原則30日。
 *    休業開始時賃金日額＝休業開始前の直近6か月間の賃金（臨時の賃金・3か月を超える期間ごとの賃金＝賞与などを除く）の総額÷180。
 *    令和9年7月31日までの額：賃金日額の上限 16,540円・下限 3,203円。30日の支給上限額 332,454円（67%）・248,100円（50%）、
 *    支給下限額 64,380円（67%）・48,045円（50%）。出生時育児休業給付金の日数は67%の180日に通算。
 *    出生後休業支援給付金の支給額＝休業開始時賃金日額×対象期間内の休業日数（28日が上限）×13%。28日の上限額 60,205円・下限額 11,658円。
 *    支給要件：① 対象期間（父・養子は出生日〜8週間を経過する日の翌日、産後休業をした母は16週間を経過する日の翌日まで）に通算14日以上の育休、
 *    ② 配偶者も出生日〜8週間を経過する日の翌日までに通算14日以上の育休、または「配偶者の育児休業を要件としない場合」（1〜7）に当たる。
 *    1頁の※2：育休中は申出により健康保険・厚生年金保険料が免除、給与が出なければ雇用保険料の負担もない。育児休業等給付は非課税。
 *    このため80%の給付率で手取り10割相当（ただし賃金日額の上限がある）。申請は原則2か月に一度。
 *  - 厚生労働省「令和８年８月１日から支給限度額が変更になります」（https://www.mhlw.go.jp/content/001728499.pdf）
 *    育児休業給付金の休業開始時の賃金月額 上限 483,300円→496,200円、下限 90,420円→96,090円。支給上限額（67%）323,811円→332,454円、
 *    （50%）241,650円→248,100円。出生後休業支援給付金（13%）58,640円→60,205円。
 *  - 厚生労働省「育児休業等給付について」（https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000135090_00001.html）
 *  - 日本年金機構「厚生年金保険料等の免除（産前産後休業・育児休業等期間）」（https://www.nenkin.go.jp/service/kounen/hokenryo/menjo/20140122-01.html）
 *    育児休業等期間の健康保険・厚生年金保険の保険料は、事業主が申し出ることで本人・事業主の両方の負担が免除。免除期間は納めた期間として扱う。
 *
 * 計算の前提（公式資料に端数の扱いの記載が無いため、この計算機で決めたこと）:
 *  - 休業開始時賃金日額は「月給×6÷180」（＝月給÷30）とし、日額の端数は切り捨てない。支給額は1円未満を切り捨てる
 *    （公式の上限額・下限額 332,454円・64,380円・60,205円・11,658円と一致する）。
 *  - 休業中に会社から賃金が出ない場合。1か月＝30日（支給単位期間）で数える。
 * 書かないこと: 休業中に賃金が出る場合の減額、パパ・ママ育休プラス、延長の条件、育児時短就業給付金。
 */

export const IKUKYU_SOURCES = {
  pamphlet: { href: "https://www.mhlw.go.jp/content/11600000/001461102.pdf", label: "厚生労働省「育児休業等給付の内容と支給申請手続」（2026年8月1日改訂版）" },
  limit: { href: "https://www.mhlw.go.jp/content/001728499.pdf", label: "厚生労働省「令和8年8月1日から支給限度額が変更になります」" },
  mhlw: { href: "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000135090_00001.html", label: "厚生労働省「育児休業等給付について」" },
  nenkin: { href: "https://www.nenkin.go.jp/service/kounen/hokenryo/menjo/20140122-01.html", label: "日本年金機構「厚生年金保険料等の免除（産前産後休業・育児休業等期間）」" },
} as const;

/** 上限額・下限額が使われる期間（2026年8月1日〜2027年7月31日。毎年8月1日に見直し） */
export const IKUKYU_PERIOD = { from: "2026年8月1日", to: "2027年7月31日" } as const;
/** 休業開始時賃金日額の上限・下限（円） */
export const DAILY_WAGE_MAX = 16_540;
export const DAILY_WAGE_MIN = 3_203;
/** 給付率（%） */
export const RATE_FIRST = 67;
export const RATE_LATER = 50;
export const RATE_SHUSSEI = 13;
/** 67%の日数（休業開始から180日）、出生後休業支援給付金の上限日数（28日）と、その対象になる最低日数（14日） */
export const FIRST_DAYS = 180;
export const SHUSSEI_MAX_DAYS = 28;
export const SHUSSEI_MIN_DAYS = 14;
/** 1か月（支給単位期間）の日数 */
export const PERIOD_DAYS = 30;

export type IkukyuInput = {
  /** 休業前6か月の月給の平均（額面。残業代・通勤手当を含み、ボーナスは除く） */
  monthly: number;
  /** 育休の日数（1か月＝30日） */
  days: number;
  /** 出生後休業支援給付金の要件に当たるか */
  shussei: boolean;
};

export type IkukyuResult = {
  /** 休業開始時賃金日額（上限・下限を当てたあと。端数あり） */
  daily: number;
  capped: "max" | "min" | null;
  /** 1か月（30日）あたり：最初の6か月（67%）とそれ以降（50%） */
  firstMonthly: number;
  laterMonthly: number;
  /** 出生後休業支援給付金（28日分まで） */
  shusseiDays: number;
  shussei: number;
  /** 育児休業給付金の合計（67%分・50%分）と、上乗せを含めた合計 */
  firstTotal: number;
  laterTotal: number;
  kyufuTotal: number;
  total: number;
  firstDays: number;
  laterDays: number;
};

/** 休業開始時賃金日額（月給×6÷180、上限16,540円・下限3,203円） */
export function dailyWage(monthly: number): { daily: number; capped: "max" | "min" | null } {
  const raw = Math.max(0, monthly) / PERIOD_DAYS;
  if (raw > DAILY_WAGE_MAX) return { daily: DAILY_WAGE_MAX, capped: "max" };
  if (raw < DAILY_WAGE_MIN) return { daily: DAILY_WAGE_MIN, capped: "min" };
  return { daily: raw, capped: null };
}

/** 日額×日数×率（%）の1円未満を切り捨て。浮動小数の誤差を避けるため、月給÷30の日額は整数のまま計算する */
function pay(monthly: number, capped: "max" | "min" | null, days: number, rate: number): number {
  if (days <= 0) return 0;
  if (capped === "max") return Math.floor((DAILY_WAGE_MAX * days * rate) / 100);
  if (capped === "min") return Math.floor((DAILY_WAGE_MIN * days * rate) / 100);
  return Math.floor((Math.max(0, monthly) * days * rate) / (100 * PERIOD_DAYS));
}

export function ikukyuKyufu(input: IkukyuInput): IkukyuResult {
  const monthly = Math.max(0, Math.floor(input.monthly));
  const days = Math.max(0, Math.floor(input.days));
  const { daily, capped } = dailyWage(monthly);
  const firstDays = Math.min(days, FIRST_DAYS);
  const laterDays = Math.max(0, days - FIRST_DAYS);
  // 1か月（30日）ごとに1円未満を切り捨てて足す（休業の終わりの月だけ日数が短い）
  const sumPeriods = (from: number, count: number, rate: number) => {
    let total = 0;
    for (let start = from; start < from + count; start += PERIOD_DAYS) total += pay(monthly, capped, Math.min(PERIOD_DAYS, from + count - start), rate);
    return total;
  };
  const firstTotal = sumPeriods(0, firstDays, RATE_FIRST);
  const laterTotal = sumPeriods(FIRST_DAYS, laterDays, RATE_LATER);
  const shusseiDays = input.shussei && days >= SHUSSEI_MIN_DAYS ? Math.min(days, SHUSSEI_MAX_DAYS) : 0;
  const shussei = pay(monthly, capped, shusseiDays, RATE_SHUSSEI);
  const kyufuTotal = firstTotal + laterTotal;
  return {
    daily,
    capped,
    firstMonthly: pay(monthly, capped, PERIOD_DAYS, RATE_FIRST),
    laterMonthly: pay(monthly, capped, PERIOD_DAYS, RATE_LATER),
    shusseiDays,
    shussei,
    firstTotal,
    laterTotal,
    kyufuTotal,
    total: kyufuTotal + shussei,
    firstDays,
    laterDays,
  };
}

/** 計算の例（ページの最初の文と計算機の最初の値）：月給30万円・育休12か月（360日）・出生後休業支援給付金あり */
export const IKUKYU_EXAMPLE: IkukyuInput = { monthly: 300_000, days: 360, shussei: true };

/** ページの表：月給ごとの、最初の6か月の月額・7か月目からの月額・28日分の上乗せ */
export const IKUKYU_EXAMPLE_MONTHLY = [200_000, 250_000, 300_000, 400_000] as const;
export function ikukyuExampleTable(): { monthly: number; result: IkukyuResult }[] {
  return IKUKYU_EXAMPLE_MONTHLY.map((monthly) => ({ monthly, result: ikukyuKyufu({ ...IKUKYU_EXAMPLE, monthly }) }));
}

/** 月給の上限・下限（賃金日額の上限・下限×30。2026年8月1日から） */
export const MONTHLY_MAX = DAILY_WAGE_MAX * PERIOD_DAYS;
export const MONTHLY_MIN = DAILY_WAGE_MIN * PERIOD_DAYS;

export function yenJa(value: number): string {
  return `${Math.round(value).toLocaleString("ja-JP")}円`;
}

/** 日数を「Nか月」「Nか月とN日」「N日」で */
export function daysJa(days: number): string {
  const m = Math.floor(days / PERIOD_DAYS);
  const d = days % PERIOD_DAYS;
  if (m === 0) return `${d}日`;
  return d === 0 ? `${m}か月` : `${m}か月と${d}日`;
}
