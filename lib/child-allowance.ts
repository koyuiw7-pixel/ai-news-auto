/**
 * 児童手当の「自分の場合」の計算（/tools/child-allowance と、児童手当の記事の中の計算機）。サーバー・ブラウザ共通、依存なし。
 * 式は tests/test_child_allowance.cjs で確かめている。2026-11-25 に公式ページで確認。
 *
 * 出典（令和6年10月分からの制度）:
 *  - こども家庭庁「もっと子育て応援！児童手当」「児童手当制度のご案内」「児童手当の基本的な取扱いについて（Q&A）」
 *    支給対象＝0歳から18歳に達する日以後の最初の3月31日までの子。月額は 3歳未満 15,000円・3歳以上高校生年代まで 10,000円、第3子以降はどちらも 30,000円。
 *    「第3子以降」＝児童と児童の兄姉等（18歳の年度末を過ぎて22歳の年度末までの、親等に経済的負担のある子）のうち、上の子から数えて3人目以降。
 *    支給は偶数月（2・4・6・8・10・12月）に、それぞれの前月分まで（2か月分）。支給日の日にちは市区町村ごとに違う（国のページには日にちの記載なし）。
 *  - こども家庭庁「児童手当制度の概要」（PDF）: 所得制限なし（拡充後・令和6年10月分以降）。多子加算のカウントは大学生に限らず、22歳年度末までの上の子で親等の経済的負担がある場合。
 *  - 児童手当法 第6条（月を単位として支給・3歳未満の数え方）、第8条（請求の翌月から・事由が消滅した月で終わる・支払期月）、第9条（減額は事由が生じた月の翌月から）
 *
 * 月の扱い（児童手当法 第6条・第8条・第9条）:
 *  - 生まれた月の分は出ない（申請した月の翌月分から。生まれてすぐ申請した場合として、生まれた月の翌月から数える）。
 *  - 3歳の誕生月までは 3歳未満の額、その翌月から 3歳以上の額（減額は事由が生じた月の翌月から）。
 *  - 18歳の年度末（3月）の分まで出る。その翌月から22歳の年度末（3月）までは、生活費を負担していれば「数に入るだけ」（手当は無い）。
 *  - 生まれた日は使わない（年と月だけ）。4月1日生まれの子は、ほかの4月生まれの子と年度の区切りが1年違うため、この計算とずれる。
 */

export const CHILD_ALLOWANCE_AMOUNTS = { under3: 15000, from3: 10000, third: 30000 } as const;

/** 支給月（偶数月）。それぞれ前の2か月分 */
export const CHILD_ALLOWANCE_PAY_MONTHS = [2, 4, 6, 8, 10, 12] as const;

/** このページの「次の支給」（2026年12月の支給＝2026年10月・11月分） */
export const CHILD_ALLOWANCE_NEXT_PAYMENT = { year: 2026, month: 12 } as const;

export type YearMonth = { year: number; month: number };

/** 年齢の区分で入れるとき */
export type ChildCategory = "under3" | "from3" | "olderSupported" | "olderNotSupported";

export const CHILD_CATEGORIES: { value: ChildCategory; label: string }[] = [
  { value: "under3", label: "3歳未満" },
  { value: "from3", label: "3歳〜高校生年代" },
  { value: "olderSupported", label: "大学生年代で生活費を負担している" },
  { value: "olderNotSupported", label: "大学生年代で負担していない・22歳の年度末を過ぎた" },
];

export type ChildInput =
  | { kind: "birth"; year: number; month: number; /** 18歳の年度末を過ぎたあと、親が生活費を負担しているか（22歳の年度末まで） */ supported?: boolean }
  | { kind: "category"; category: ChildCategory };

/** その月の子の立場 */
export type ChildStatus =
  | "notBorn" // まだ生まれていない、または生まれた月（その月の分は出ない）
  | "under3" // 3歳未満（手当あり）
  | "from3" // 3歳以上・高校生年代まで（手当あり）
  | "olderCounted" // 18歳の年度末を過ぎて22歳の年度末まで・生活費を負担（数に入るが手当なし）
  | "olderNotCounted" // 18歳の年度末を過ぎて22歳の年度末まで・負担なし（数に入らない）
  | "over22"; // 22歳の年度末を過ぎた（数に入らない）

export type ChildMonth = {
  status: ChildStatus;
  /** 第何子（数に入らない子は null） */
  rank: number | null;
  amount: number;
};

const index = (ym: YearMonth) => ym.year * 12 + (ym.month - 1);
const fromIndex = (i: number): YearMonth => ({ year: Math.floor(i / 12), month: (i % 12) + 1 });

/** 年度の始まりの年（4〜12月生まれはその年、1〜3月生まれは前の年。4月1日生まれは考えない） */
export function schoolYearOf(year: number, month: number): number {
  return month >= 4 ? year : year - 1;
}

/** 生まれた年月から、その月の立場 */
export function statusByBirth(child: { year: number; month: number; supported?: boolean }, ym: YearMonth): ChildStatus {
  const now = index(ym);
  const birth = index({ year: child.year, month: child.month });
  if (now <= birth) return "notBorn";
  const fy = schoolYearOf(child.year, child.month);
  const end18 = index({ year: fy + 19, month: 3 }); // 18歳に達する日以後の最初の3月31日の月
  const end22 = index({ year: fy + 23, month: 3 }); // 22歳に達する日以後の最初の3月31日の月
  if (now <= end18) return now <= index({ year: child.year + 3, month: child.month }) ? "under3" : "from3";
  if (now <= end22) return child.supported ? "olderCounted" : "olderNotCounted";
  return "over22";
}

function statusOf(child: ChildInput, ym: YearMonth): ChildStatus {
  if (child.kind === "birth") return statusByBirth(child, ym);
  if (child.category === "olderSupported") return "olderCounted";
  if (child.category === "olderNotSupported") return "olderNotCounted";
  return child.category;
}

/** 上の子からの並び（生まれた年月が早い順。区分で入れた子は区分の順、同じなら入れた順） */
function ageKey(child: ChildInput): number {
  if (child.kind === "birth") return index({ year: child.year, month: child.month });
  // 区分で入れた子は生まれた年月の代わりに区分の順を使う（上の区分ほど小さい）
  return { olderSupported: -3e6, olderNotSupported: -3e6, from3: -2e6, under3: -1e6 }[child.category];
}

/**
 * ある月の、子ども一人ひとりの立場・第何子・手当の月額（入れた順のまま返す）。
 * 第何子は、手当の対象の子と「数に入る」上の子（22歳の年度末まで・生活費を負担）だけで、上の子から数える。
 */
export function allowanceForMonth(children: ChildInput[], ym: YearMonth): ChildMonth[] {
  const statuses = children.map((child) => statusOf(child, ym));
  const order = children.map((child, i) => ({ i, key: ageKey(child) })).sort((a, b) => a.key - b.key || a.i - b.i);
  const result: ChildMonth[] = statuses.map((status) => ({ status, rank: null, amount: 0 }));
  let rank = 0;
  for (const { i } of order) {
    const status = statuses[i];
    if (status !== "under3" && status !== "from3" && status !== "olderCounted") continue;
    rank += 1;
    result[i].rank = rank;
    if (status === "olderCounted") continue;
    result[i].amount = rank >= 3 ? CHILD_ALLOWANCE_AMOUNTS.third : status === "under3" ? CHILD_ALLOWANCE_AMOUNTS.under3 : CHILD_ALLOWANCE_AMOUNTS.from3;
  }
  return result;
}

export function monthTotal(children: ChildInput[], ym: YearMonth): number {
  return allowanceForMonth(children, ym).reduce((sum, c) => sum + c.amount, 0);
}

export type Payment = {
  /** 支給の月（偶数月） */
  pay: YearMonth;
  /** その支給に入る2か月 */
  months: [YearMonth, YearMonth];
  amount: number;
};

/** 偶数月の支給1回分（前の2か月分の合計） */
export function paymentFor(children: ChildInput[], pay: YearMonth): Payment {
  if (!CHILD_ALLOWANCE_PAY_MONTHS.includes(pay.month as (typeof CHILD_ALLOWANCE_PAY_MONTHS)[number])) {
    throw new Error(`支給は偶数月だけ: ${pay.year}-${pay.month}`);
  }
  const p = index(pay);
  const months: [YearMonth, YearMonth] = [fromIndex(p - 2), fromIndex(p - 1)];
  return { pay, months, amount: monthTotal(children, months[0]) + monthTotal(children, months[1]) };
}

/** pay から数えて n 回分の支給（2か月ごと） */
export function paymentsFrom(children: ChildInput[], pay: YearMonth, n = 6): Payment[] {
  const p = index(pay);
  return Array.from({ length: n }, (_, k) => paymentFor(children, fromIndex(p + 2 * k)));
}

export type ChildAllowanceResult = {
  /** 次の支給のいちばん新しい月（12月の支給なら11月）の、子ども一人ひとり */
  children: ChildMonth[];
  /** その月の合計 */
  monthly: number;
  /** 次の支給（12月の支給＝10月・11月分） */
  next: Payment;
  /** 次の支給から1年分（6回・12か月分） */
  year: { payments: Payment[]; total: number };
};

export function childAllowance(children: ChildInput[], pay: YearMonth = CHILD_ALLOWANCE_NEXT_PAYMENT): ChildAllowanceResult {
  const payments = paymentsFrom(children, pay, 6);
  const latest = payments[0].months[1];
  return {
    children: allowanceForMonth(children, latest),
    monthly: monthTotal(children, latest),
    next: payments[0],
    year: { payments, total: payments.reduce((sum, p) => sum + p.amount, 0) },
  };
}

/** 結果の欄の短い説明（第何子・立場） */
export function statusLabel(c: ChildMonth): string {
  switch (c.status) {
    case "notBorn":
      return "まだ対象の月ではありません";
    case "under3":
      return `第${c.rank}子・3歳未満`;
    case "from3":
      return `第${c.rank}子・3歳〜高校生年代`;
    case "olderCounted":
      return `第${c.rank}子として数える（手当はありません）`;
    case "olderNotCounted":
      return "数に入りません（生活費の負担なし）";
    case "over22":
      return "数に入りません（22歳の年度末を過ぎています）";
  }
}

/** 「よくある家族の例」の表。区分で入れた子（上の子から）。数字はすべて childAllowance() で出す */
export const CHILD_ALLOWANCE_EXAMPLES: { label: string; children: ChildCategory[] }[] = [
  { label: "3歳未満が1人", children: ["under3"] },
  { label: "小学生が1人", children: ["from3"] },
  { label: "小学生と3歳未満", children: ["from3", "under3"] },
  { label: "小学生2人と3歳未満", children: ["from3", "from3", "under3"] },
  { label: "高校生・中学生・小学生", children: ["from3", "from3", "from3"] },
  { label: "大学生（生活費を負担）・高校生・中学生", children: ["olderSupported", "from3", "from3"] },
  { label: "大学生（負担なし）・高校生・中学生", children: ["olderNotSupported", "from3", "from3"] },
];

export function childAllowanceExampleTable(): { label: string; monthly: number; payment: number; year: number }[] {
  return CHILD_ALLOWANCE_EXAMPLES.map((example) => {
    const r = childAllowance(example.children.map((category) => ({ kind: "category", category }) as const));
    return { label: example.label, monthly: r.monthly, payment: r.next.amount, year: r.year.total };
  });
}

/** 2026年12月 → "2026年12月" */
export function ymJa(ym: YearMonth): string {
  return `${ym.year}年${ym.month}月`;
}
