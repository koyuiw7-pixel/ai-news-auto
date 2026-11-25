/**
 * 年金生活者支援給付金の「自分の場合」の計算（/tools/pension-support-benefit と、年金生活者支援給付金の記事の中の計算機）。サーバー・ブラウザ共通、依存なし。
 * 式は tests/test_pension_support_benefit.cjs で確かめている。2026-11-26 に公式ページで確認。
 *
 * 出典（令和8年度の額・令和8年10月分から令和9年9月分までの判定）:
 *  - 日本年金機構「老齢（補足的老齢）年金生活者支援給付金」（更新日 2026年10月1日）
 *    支給要件＝65歳以上で老齢基礎年金を受けている・世帯全員の市町村民税が非課税・前年の年金収入金額とその他の所得の合計が基準以下。
 *    前年＝令和8年10月分から令和9年9月分までは令和7年。年金収入金額に障害年金・遺族年金等の非課税収入は含まれない。
 *    昭和31年4月2日以後生まれ: 826,500円以下は老齢、826,500円を超え926,500円以下は補足的老齢。
 *    昭和31年4月1日以前生まれ: 824,100円以下は老齢、824,100円を超え924,100円以下は補足的老齢。
 *    老齢＝(1) 5,620円×保険料納付済期間÷480月 ＋ (2) 11,768円×保険料免除期間÷480月（全額・4分の3・半額免除。4分の1免除は5,884円）。
 *    昭和31年4月1日以前生まれは 11,734円・5,867円。昭和16年4月1日以前生まれは480月を生年月日に応じて短くする（数字は載っていない）。
 *    補足的老齢＝5,620円×保険料納付済期間÷480月×調整支給率（(926,500円－前年の年金収入金額とその他の所得の合計)÷100,000円。昭和31年4月1日以前生まれは924,100円）。
 *    それぞれの計算結果の50銭未満は切り捨て、50銭以上1円未満は1円に切り上げ。
 *  - 日本年金機構「障害年金生活者支援給付金」（更新日 2026年10月1日）: 障害基礎年金を受けている・前年の所得が 4,918,000円＋扶養親族の数×38万円 以下。
 *    1級 7,025円・2級 5,620円（月額）。扶養親族は 70歳以上の同一生計配偶者・老人扶養親族は48万円、特定扶養親族・16歳以上19歳未満は63万円。
 *  - 日本年金機構「遺族年金生活者支援給付金」（更新日 2026年10月1日）: 遺族基礎年金を受けている・所得基準は障害と同じ。5,620円（月額）。
 *    2人以上の子が遺族基礎年金を受けている場合は、5,620円を子の人数で割った額をそれぞれに（50銭の扱いは同じ）。
 *  - 日本年金機構「令和8年4月分からの年金生活者支援給付金額について」（2026年4月1日）: 令和8年度の基準額 5,620円（令和7年度 5,450円）、障害1級 7,025円。
 *  - 日本年金機構「年金生活者支援給付金制度について」: 原則、偶数月の中旬に2カ月分（前月および前々月）を年金と同じ受取口座に、年金とは別に支払う。
 *
 * 注意: 日本年金機構の年金Q&A（kaiteitsuchi/keisan.html）の調整支給率は 909,000円（昭和31年4月1日以前生まれ 906,700円）のまま。
 * これは令和8年9月分までの判定の数字で、令和8年10月分からは制度の案内ページ（rourei.html、2026年10月1日更新）の 926,500円・924,100円を使う。
 */

export type PensionKind = "old" | "disability" | "survivor";
export type Answer = "yes" | "no" | "unknown";
/** 生年月日の区分。after＝昭和31年（1956年）4月2日以後、before＝昭和16年4月2日〜昭和31年4月1日、veryOld＝昭和16年（1941年）4月1日以前 */
export type BirthGroup = "after" | "before" | "veryOld";

/** 令和8年度（令和8年4月分〜令和9年3月分）の額。判定の基準額は令和8年10月分〜令和9年9月分（前年＝令和7年の収入・所得） */
export const PENSION_SUPPORT = {
  fiscalYear: "令和8年度",
  /** 老齢の保険料納付済期間に掛ける額（基準額）・障害2級・遺族 */
  base: 5620,
  disability1: 7025,
  disability2: 5620,
  survivor: 5620,
  months: 480,
  /** 保険料免除期間に掛ける額（全額・4分の3・半額免除＝老齢基礎年金満額の6分の1、4分の1免除＝12分の1） */
  exempt: { after: { full: 11768, quarter: 5884 }, before: { full: 11734, quarter: 5867 } },
  /** 老齢の所得の基準（以下なら老齢、超えて upper 以下なら補足的老齢） */
  threshold: { after: { base: 826500, upper: 926500 }, before: { base: 824100, upper: 924100 } },
  supplementDivisor: 100000,
  /** 障害・遺族の所得の基準 */
  incomeLimit: 4918000,
  dependent: { general: 380000, elderly: 480000, specified: 630000 },
} as const;

/** 判定に使う前年と、その判定が使われる期間 */
export const PENSION_SUPPORT_PERIOD = { incomeYear: "令和7年（2025年）", span: "令和8年（2026年）10月分から令和9年（2027年）9月分まで" } as const;

/** このページの「次の支払い」（2026年12月の支払い＝10月・11月分） */
export const PENSION_SUPPORT_NEXT_PAYMENT = { year: 2026, month: 12, months: [10, 11] } as const;

/** 問い合わせ先（日本年金機構のページの記載どおり。2026-11-26 確認） */
export const PENSION_SUPPORT_CONTACTS = {
  kyufukin: { label: "給付金専用ダイヤル", number: "0570-05-4092", alt: "03-5539-2216", altNote: "050で始まる電話からは（東京）" },
  nenkin: { label: "ねんきんダイヤル", number: "0570-05-1165", alt: "03-6700-1165", altNote: "050で始まる電話からは（東京）" },
  hours: "月曜日 8時30分〜19時、火曜日〜金曜日 8時30分〜17時15分、第2土曜日 9時30分〜16時（祝日、ほかの土曜日・日曜日、12月29日〜1月3日は休み）",
} as const;

/** はがき型の請求書を令和9年1月4日（月曜）までに日本年金機構へ届くよう出せば、令和8年10月分からさかのぼる */
export const PENSION_SUPPORT_HAGAKI_DEADLINE = "令和9年（2027年）1月4日（月曜）";

export type Dependents = { general: number; elderly: number; specified: number };

export type OldAgeInput = {
  kind: "old";
  /** 65歳以上で老齢基礎年金を受けている */
  age65: boolean;
  /** 世帯全員の市町村民税が非課税か */
  household: Answer;
  birth: BirthGroup;
  /** 前年の公的年金等の収入金額（障害年金・遺族年金は入れない） */
  pensionIncome: number;
  /** 前年のその他の所得 */
  otherIncome: number;
  /** 保険料納付済期間（月数） */
  paidMonths: number;
  /** 全額・4分の3・半額免除の月数 */
  exemptFullMonths: number;
  /** 4分の1免除の月数 */
  exemptQuarterMonths: number;
};

export type DisabilityInput = { kind: "disability"; grade: 1 | 2; income: number; dependents: Dependents };
/** sharing は遺族基礎年金を受けている人数（配偶者が受けているか子が1人なら1。2人以上の子が受けていればその人数） */
export type SurvivorInput = { kind: "survivor"; sharing: number; income: number; dependents: Dependents };
export type PensionSupportInput = OldAgeInput | DisabilityInput | SurvivorInput;

export type Verdict = "eligible" | "supplement" | "ineligible" | "check";

export const VERDICT_LABELS: Record<Verdict, string> = {
  eligible: "対象の目安",
  supplement: "補足的給付の目安",
  ineligible: "対象外の目安",
  check: "確かめる必要あり",
};

export type PensionSupportResult = {
  verdict: Verdict;
  /** 給付の名前（老齢年金生活者支援給付金など） */
  benefit: string;
  /** 月額。出せないときは null（対象外は 0） */
  monthly: number | null;
  /** 1回の支払い（2か月分） */
  perPayment: number | null;
  /** 1年分（令和8年度の額のまま12か月） */
  annual: number | null;
  /** 判定の理由（短い文） */
  reasons: string[];
  /** 計算の式（数字入り） */
  steps: string[];
};

/** 分数 num/den を、50銭未満は切り捨て・50銭以上は1円に切り上げて円にする（num・den は0以上の整数） */
export function roundYen(num: number, den: number): number {
  return Math.floor((2 * num + den) / (2 * den));
}

const comma = (n: number) => `${n.toLocaleString("ja-JP")}円`;

/** 障害・遺族の所得の基準額（4,918,000円＋扶養親族の数に応じた額） */
export function incomeLimitFor(dependents: Dependents): number {
  const d = PENSION_SUPPORT.dependent;
  return PENSION_SUPPORT.incomeLimit + dependents.general * d.general + dependents.elderly * d.elderly + dependents.specified * d.specified;
}

/** 老齢年金生活者支援給付金の月額（(1)納付済期間の分＋(2)免除期間の分） */
export function oldAgeAmount(birth: "after" | "before", paidMonths: number, exemptFullMonths: number, exemptQuarterMonths: number) {
  const P = PENSION_SUPPORT;
  const e = P.exempt[birth];
  const paid = roundYen(P.base * paidMonths, P.months);
  const exempt = roundYen(e.full * exemptFullMonths, P.months) + roundYen(e.quarter * exemptQuarterMonths, P.months);
  return { paid, exempt, total: paid + exempt };
}

/** 補足的老齢年金生活者支援給付金の月額（5,620円×納付済期間÷480月×調整支給率） */
export function supplementAmount(birth: "after" | "before", paidMonths: number, income: number): number {
  const P = PENSION_SUPPORT;
  const upper = P.threshold[birth].upper;
  if (income > upper) return 0;
  return roundYen(P.base * paidMonths * (upper - income), P.months * P.supplementDivisor);
}

function withAmount(verdict: Verdict, benefit: string, monthly: number | null, reasons: string[], steps: string[]): PensionSupportResult {
  return {
    verdict,
    benefit,
    monthly,
    perPayment: monthly === null ? null : monthly * 2,
    annual: monthly === null ? null : monthly * 12,
    reasons,
    steps,
  };
}

function oldAge(input: OldAgeInput): PensionSupportResult {
  const P = PENSION_SUPPORT;
  const name = "老齢年金生活者支援給付金";
  const months = input.paidMonths + input.exemptFullMonths + input.exemptQuarterMonths;
  if (!input.age65) {
    return withAmount("ineligible", name, 0, ["老齢の給付金は、65歳以上で老齢基礎年金を受けている方が対象です。"], []);
  }
  if (input.household === "no") {
    return withAmount("ineligible", name, 0, ["世帯のだれかに市町村民税がかかっていると、老齢の給付金は受け取れません。"], []);
  }
  if (months > P.months) {
    return withAmount("check", name, null, [`納めた月数と免除の月数の合計が${P.months}か月を超えています。年金証書や支給額変更通知書で月数を確かめてください。`], []);
  }
  if (input.birth === "veryOld") {
    return withAmount(
      "check",
      name,
      null,
      ["昭和16年4月1日以前に生まれた方は、生年月日に応じて480月を短くして計算するため、ここでは金額を出していません。所得の基準は昭和31年4月1日以前生まれの方と同じです。"],
      [],
    );
  }
  const birth = input.birth;
  const income = input.pensionIncome + input.otherIncome;
  const t = P.threshold[birth];
  const reasons: string[] = [];
  const unknown = input.household === "unknown";
  if (unknown) reasons.push("世帯全員が市町村民税の非課税かどうかで決まります。お住まいの市区町村で確かめてください。下の金額は、非課税だった場合です。");
  if (income > t.upper) {
    return withAmount("ineligible", name, 0, [`前年の年金収入とその他の所得の合計（${comma(income)}）が${comma(t.upper)}を超えています。`], []);
  }
  if (income <= t.base) {
    const a = oldAgeAmount(birth, input.paidMonths, input.exemptFullMonths, input.exemptQuarterMonths);
    const e = P.exempt[birth];
    const steps = [`${comma(P.base)}×${input.paidMonths}か月÷${P.months}月＝${comma(a.paid)}（納めた期間の分）`];
    if (input.exemptFullMonths > 0) steps.push(`${comma(e.full)}×${input.exemptFullMonths}か月÷${P.months}月＝${comma(roundYen(e.full * input.exemptFullMonths, P.months))}（全額・4分の3・半額免除の分）`);
    if (input.exemptQuarterMonths > 0) steps.push(`${comma(e.quarter)}×${input.exemptQuarterMonths}か月÷${P.months}月＝${comma(roundYen(e.quarter * input.exemptQuarterMonths, P.months))}（4分の1免除の分）`);
    reasons.unshift(`前年の年金収入とその他の所得の合計（${comma(income)}）が${comma(t.base)}以下です。`);
    return withAmount(unknown ? "check" : "eligible", name, a.total, reasons, steps);
  }
  const amount = supplementAmount(birth, input.paidMonths, income);
  const steps = [
    `調整支給率＝（${comma(t.upper)}－${comma(income)}）÷${comma(P.supplementDivisor)}`,
    `${comma(P.base)}×${input.paidMonths}か月÷${P.months}月×調整支給率＝${comma(amount)}`,
  ];
  reasons.unshift(`前年の年金収入とその他の所得の合計（${comma(income)}）が${comma(t.base)}を超え${comma(t.upper)}以下なので、補足的老齢年金生活者支援給付金の目安です。免除の期間は計算に入りません。`);
  return withAmount(unknown ? "check" : "supplement", "補足的老齢年金生活者支援給付金", amount, reasons, steps);
}

function flat(input: DisabilityInput | SurvivorInput): PensionSupportResult {
  const P = PENSION_SUPPORT;
  const limit = incomeLimitFor(input.dependents);
  const name = input.kind === "disability" ? "障害年金生活者支援給付金" : "遺族年金生活者支援給付金";
  if (input.income > limit) {
    return withAmount("ineligible", name, 0, [`前年の所得（${comma(input.income)}）が基準額（${comma(limit)}）を超えています。`], []);
  }
  const reasons = [`前年の所得（${comma(input.income)}）が基準額（${comma(limit)}）以下です。`];
  if (input.kind === "disability") {
    const monthly = input.grade === 1 ? P.disability1 : P.disability2;
    return withAmount("eligible", name, monthly, reasons, [`障害等級${input.grade}級の月額＝${comma(monthly)}`]);
  }
  const n = Math.max(1, Math.floor(input.sharing));
  const monthly = roundYen(P.survivor, n);
  const steps = n > 1 ? [`${comma(P.survivor)}÷子${n}人＝${comma(monthly)}（1人あたり）`] : [`月額＝${comma(monthly)}`];
  return withAmount("eligible", name, monthly, reasons, steps);
}

export function pensionSupport(input: PensionSupportInput): PensionSupportResult {
  return input.kind === "old" ? oldAge(input) : flat(input);
}

/** 「40年納めた」などの入れ方から月数へ */
export function yearsToMonths(years: number): number {
  return Math.round(years * 12);
}

const NO_DEPENDENTS: Dependents = { general: 0, elderly: 0, specified: 0 };
const old = (paidMonths: number, income: number, exemptFullMonths = 0): OldAgeInput => ({
  kind: "old",
  age65: true,
  household: "yes",
  birth: "after",
  pensionIncome: income,
  otherIncome: 0,
  paidMonths,
  exemptFullMonths,
  exemptQuarterMonths: 0,
});

/** 「よくある例」の表。数字はすべて pensionSupport() で出す（世帯全員が非課税・昭和31年4月2日以後生まれ） */
export const PENSION_SUPPORT_EXAMPLES: { label: string; input: PensionSupportInput }[] = [
  { label: "老齢：40年すべて納めた・年金収入70万円", input: old(480, 700000) },
  { label: "老齢：30年納めた・10年全額免除・年金収入70万円", input: old(360, 700000, 120) },
  { label: "老齢：20年納めた・5年全額免除・年金収入60万円", input: old(240, 600000, 60) },
  { label: "老齢：40年すべて納めた・年金収入87万6,500円", input: old(480, 876500) },
  { label: "老齢：40年すべて納めた・年金収入95万円", input: old(480, 950000) },
  { label: "障害基礎年金1級・前年の所得200万円", input: { kind: "disability", grade: 1, income: 2000000, dependents: NO_DEPENDENTS } },
  { label: "障害基礎年金2級・前年の所得200万円", input: { kind: "disability", grade: 2, income: 2000000, dependents: NO_DEPENDENTS } },
  { label: "遺族基礎年金を子2人が受けている（1人あたり）", input: { kind: "survivor", sharing: 2, income: 0, dependents: NO_DEPENDENTS } },
];

export function pensionSupportExampleTable(): { label: string; verdict: string; monthly: number; perPayment: number; annual: number }[] {
  return PENSION_SUPPORT_EXAMPLES.map((example) => {
    const r = pensionSupport(example.input);
    return { label: example.label, verdict: VERDICT_LABELS[r.verdict], monthly: r.monthly ?? 0, perPayment: r.perPayment ?? 0, annual: r.annual ?? 0 };
  });
}

/** 判定ごとの次にすること（日本年金機構の案内どおり） */
export function nextSteps(input: PensionSupportInput, result: PensionSupportResult): string[] {
  const c = PENSION_SUPPORT_CONTACTS;
  const call = `わからないときは、${c.kyufukin.label}（${c.kyufukin.number}。${c.kyufukin.altNote}${c.kyufukin.alt}）か、お近くの年金事務所へ。`;
  if (result.verdict === "ineligible") {
    if (input.kind === "old" && !input.age65) {
      return ["65歳になる3カ月前に、年金請求書（事前送付用）に給付金の請求書が同封されて届きます。65歳の誕生日の前日以降に、年金の請求書と一緒に年金事務所に出します。", call];
    }
    return ["判定は毎年、前年の所得などで決まり直し、10月分から翌年9月分まで反映されます。収入や世帯が変わった年は、もう一度確かめてください。", call];
  }
  if (input.kind === "old") {
    return [
      `すでに年金を受けていて新しく受け取れる方には、毎年9月の第1営業日から順に「年金生活者支援給付金請求書（はがき型）」が届きます。切手を貼ってポストに出すか、電子申請で出せます。`,
      `${PENSION_SUPPORT_HAGAKI_DEADLINE}までに日本年金機構へ届くよう手続きすれば、令和8年10月分からさかのぼって受け取れます。過ぎても手続きはできますが、原則として請求した月の翌月分からです。`,
      "65歳になる方は、年金請求書（事前送付用）に同封される給付金の請求書を、年金の請求書と一緒に年金事務所に出します。",
      call,
    ];
  }
  return [
    "障害基礎年金・遺族基礎年金を新しく請求する方は、年金の請求のときに「年金生活者支援給付金請求書（A4型）」をあわせて出します。",
    "原則として、手続きをした翌月分から支給の対象になります。年金を受ける権利ができてから3カ月以内に請求すれば、その日までさかのぼります。",
    call,
  ];
}
