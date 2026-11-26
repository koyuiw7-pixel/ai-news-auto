/**
 * 高額療養費の「1か月の自己負担の上限額」の計算（/tools/kogaku-ryoyohi と、見出しに「高額療養費」がある記事の中の計算機）。サーバー・ブラウザ共通、依存なし。
 * 式は tests/test_kogaku_ryoyohi.cjs で確かめている。2026-11-26 に公式資料で確認。
 *
 * 出典:
 *  - 厚生労働省「高額療養費制度の見直しについて（令和８年８月診療分から）」（https://www.mhlw.go.jp/content/001726232.pdf）
 *    「患者負担割合及び高額療養費自己負担限度額（令和８年８月～令和９年７月）」の表。70歳未満・70歳以上の月単位の上限額、多数回該当、年単位の上限額。
 *    令和9年8月からは所得区分が細かくなる（別の表）。この計算機は令和8年8月〜令和9年7月診療分だけを扱う。
 *  - 厚生労働省「高額療養費制度を利用される皆さまへ」（https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/juuyou/kougakuiryou/index.html）
 *    多数回該当（直近12か月に3か月以上 → 4か月目から）、年間上限（8月〜翌年7月）、マイナ保険証か限度額適用認定証で窓口の支払いが上限まで。
 *  - 全国健康保険協会（協会けんぽ）「高額療養費」（https://www.kyoukaikenpo.or.jp/benefit/high_cost_medical_expenses/002/index.html）
 *    区分ア〜オの表（令和8年8月～令和9年7月）、世帯合算（70歳未満は1つの医療機関の自己負担21,000円以上）、
 *    年間上限額の申請は令和9年8月から、標準報酬月額15万円以下は年間上限41万円を令和9年8月以降に償還払い、食事代・差額ベッド代は対象外。
 *  - 協会けんぽ「限度額適用認定証」（https://www.kyoukaikenpo.or.jp/benefit/high_cost_medical_expenses/001/index.html）
 *    マイナ保険証なら申請不要。住民税非課税の人はマイナ保険証でも「限度額適用・標準負担額減額認定証」の申請が必要。
 *
 * 書かないこと（公式資料で確かめられなかったため）: 申請の期限、1円未満の端数の公式の扱い、国保・健保組合ごとの申請先と申請の開始時期。
 */

export const KOGAKU_PERIOD = { from: "2026年8月診療分", to: "2027年7月診療分", fromJa: "令和8年8月", toJa: "令和9年7月" } as const;

export const KOGAKU_SOURCES = {
  mhlwPdf: { href: "https://www.mhlw.go.jp/content/001726232.pdf", label: "厚生労働省「高額療養費制度の見直しについて（令和８年８月診療分から）」" },
  mhlw: {
    href: "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/juuyou/kougakuiryou/index.html",
    label: "厚生労働省「高額療養費制度を利用される皆さまへ」",
  },
  kyokai: { href: "https://www.kyoukaikenpo.or.jp/benefit/high_cost_medical_expenses/002/index.html", label: "全国健康保険協会（協会けんぽ）「高額療養費」" },
  nintei: { href: "https://www.kyoukaikenpo.or.jp/benefit/high_cost_medical_expenses/001/index.html", label: "協会けんぽ「限度額適用認定証」" },
} as const;

export type KogakuAge = "under70" | "70to74" | "75plus";
export type KogakuBand = "a" | "i" | "u" | "e" | "o" | "low1";

/** 所得の区分（年収は厚生労働省の資料の「年収換算」。区分は健康保険の標準報酬月額・国保の所得で決まる） */
export type KogakuBandInfo = {
  key: KogakuBand;
  /** 選ぶときの名前（年収の目安） */
  label: string;
  /** 区分の正式な決まり方（69歳まで） */
  detail: string;
  /** 区分の正式な決まり方（70歳以上） */
  seniorDetail?: string;
  /** 70歳未満の区分の名前（協会けんぽの ア〜オ）。70歳以上だけの区分は undefined */
  letter?: string;
  /** 70歳以上の区分の名前 */
  senior?: string;
  /** 月の上限（世帯ごと・入院を含む）＝ base＋(総医療費−threshold)×1%。threshold が無ければ定額 */
  base: number;
  threshold?: number;
  /** 多数回該当（4か月目から）の上限。無い区分は undefined */
  many?: number;
  /** 年単位の上限額（8月〜翌年7月） */
  yearly: number;
  /** 70歳以上の外来（個人ごと）の上限と、その年間上限。現役並みの区分には無い */
  outpatient?: number;
  outpatientYearly?: number;
  /** 70歳未満だけ／70歳以上だけの区分 */
  under70: boolean;
  over70: boolean;
};

export const KOGAKU_BANDS: readonly KogakuBandInfo[] = [
  {
    key: "a",
    label: "年収約1,160万円以上",
    detail: "健康保険は標準報酬月額83万円以上、国民健康保険は旧ただし書き所得901万円超",
    seniorDetail: "健康保険は標準報酬月額83万円以上、国民健康保険・後期高齢者医療は課税所得690万円以上",
    letter: "ア",
    senior: "現役並み所得（年収約1,160万円以上）",
    base: 270300,
    threshold: 901000,
    many: 140100,
    yearly: 1680000,
    under70: true,
    over70: true,
  },
  {
    key: "i",
    label: "年収約770万〜約1,160万円",
    detail: "健康保険は標準報酬月額53万〜79万円、国民健康保険は旧ただし書き所得600万〜901万円",
    seniorDetail: "健康保険は標準報酬月額53万〜79万円、国民健康保険・後期高齢者医療は課税所得380万円以上",
    letter: "イ",
    senior: "現役並み所得（年収約770万〜約1,160万円）",
    base: 179100,
    threshold: 597000,
    many: 93000,
    yearly: 1110000,
    under70: true,
    over70: true,
  },
  {
    key: "u",
    label: "年収約370万〜約770万円",
    detail: "健康保険は標準報酬月額28万〜50万円、国民健康保険は旧ただし書き所得210万〜600万円",
    seniorDetail: "健康保険は標準報酬月額28万〜50万円、国民健康保険・後期高齢者医療は課税所得145万円以上",
    letter: "ウ",
    senior: "現役並み所得（年収約370万〜約770万円）",
    base: 85800,
    threshold: 286000,
    many: 44400,
    yearly: 530000,
    under70: true,
    over70: true,
  },
  {
    key: "e",
    label: "年収約370万円まで",
    detail: "健康保険は標準報酬月額26万円以下、国民健康保険は旧ただし書き所得210万円以下",
    seniorDetail: "健康保険は標準報酬月額26万円以下、国民健康保険・後期高齢者医療は課税所得145万円未満",
    letter: "エ",
    senior: "一般（年収約370万円まで）",
    base: 61500,
    many: 44400,
    yearly: 530000,
    outpatient: 22000,
    outpatientYearly: 216000,
    under70: true,
    over70: true,
  },
  {
    key: "o",
    label: "住民税が非課税",
    detail: "住民税が非課税の世帯",
    letter: "オ",
    senior: "住民税が非課税（低所得者Ⅱ）",
    base: 36900,
    many: 24600,
    yearly: 290000,
    under70: true,
    over70: false,
  },
  {
    key: "o",
    label: "住民税が非課税",
    detail: "住民税が非課税の世帯（低所得者Ⅱ）",
    senior: "住民税が非課税（低所得者Ⅱ）",
    base: 25700,
    many: 24600,
    yearly: 290000,
    outpatient: 11000,
    outpatientYearly: 96000,
    under70: false,
    over70: true,
  },
  {
    key: "low1",
    label: "住民税が非課税で、所得が一定以下",
    detail: "住民税が非課税かつ所得が一定以下（低所得者Ⅰ。協会けんぽでは、被保険者と扶養家族すべての収入から必要経費・控除額を除いた後の所得がない人）",
    senior: "住民税が非課税で所得が一定以下（低所得者Ⅰ）",
    base: 15700,
    yearly: 180000,
    outpatient: 8000,
    under70: false,
    over70: true,
  },
];

/** 年齢ごとに選べる区分（上から年収の高い順） */
export function bandsFor(age: KogakuAge): KogakuBandInfo[] {
  return KOGAKU_BANDS.filter((b) => (age === "under70" ? b.under70 : b.over70));
}

export function bandOf(age: KogakuAge, key: KogakuBand): KogakuBandInfo {
  const list = bandsFor(age);
  return list.find((b) => b.key === key) ?? list[list.length - 1];
}

/** 窓口の負担割合。70歳未満は3割（義務教育就学前は2割）。70歳以上の現役並みは3割。それ以外の70〜74歳は2割、75歳以上は1割（一定以上の所得なら2割） */
export function defaultShare(age: KogakuAge, band: KogakuBand): number {
  if (age === "under70") return 0.3;
  if (band === "a" || band === "i" || band === "u") return 0.3;
  return age === "70to74" ? 0.2 : 0.1;
}

/** 計算機に最初に入っている総医療費（10割）。読者は入院前に総医療費を知らないので、まず100万円のときの上限を見せる */
export const KOGAKU_DEFAULT_TOTAL = 1_000_000;

const safe = (value: number | undefined) => (value !== undefined && Number.isFinite(value) && value > 0 ? value : 0);

/** 月の上限額（世帯ごと・入院を含む）。1%の部分は1円未満を四捨五入して表示用にそろえる（公式の端数の扱いは資料に無い） */
export function monthlyCap(band: KogakuBandInfo, totalMedical: number): number {
  if (band.threshold === undefined) return band.base;
  return Math.round(band.base + Math.max(0, safe(totalMedical) - band.threshold) * 0.01);
}

export type KogakuInput = {
  age: KogakuAge;
  band: KogakuBand;
  /** 1か月の総医療費（保険がきく医療費の10割）。入れなければ100万円で計算 */
  totalMedical?: number;
  /** 直近12か月に、上限に達した月がすでに3か月以上ある（4か月目から＝多数回該当） */
  many?: boolean;
  /** 70歳以上で、その月が外来（通院）だけ */
  outpatientOnly?: boolean;
  /** 窓口の負担割合（0.1〜0.3）。入れなければ年齢と区分の初期値 */
  share?: number;
};

export type KogakuResult = {
  band: KogakuBandInfo;
  totalMedical: number;
  /** 総医療費を入れたか（false なら100万円で計算した目安） */
  entered: boolean;
  share: number;
  /** その月の上限（多数回・外来だけを反映） */
  cap: number;
  /** 上限の種類の説明 */
  capLabel: string;
  /** 定額の上限か（総医療費で変わらない） */
  fixed: boolean;
  /** 1回目〜3回目の上限（多数回でないとき） */
  normalCap: number;
  /** 4か月目からの上限（無い区分は undefined） */
  manyCap?: number;
  /** 窓口の負担割合どおりに払った場合の額 */
  windowShare: number;
  /** 実際の1か月の自己負担（窓口の負担と上限の小さいほう） */
  pay: number;
  /** 上限を超えた分（払い戻し、またはマイナ保険証・認定証で窓口で払わずに済む分） */
  over: number;
  yearly: number;
  outpatientYearly?: number;
};

export function kogaku(input: KogakuInput): KogakuResult {
  const band = bandOf(input.age, input.band);
  const entered = safe(input.totalMedical) > 0;
  const totalMedical = entered ? safe(input.totalMedical) : KOGAKU_DEFAULT_TOTAL;
  const share = input.share && input.share > 0 && input.share <= 0.3 ? input.share : defaultShare(input.age, band.key);
  const normalCap = monthlyCap(band, totalMedical);
  const manyCap = band.many;
  const outpatient = input.age !== "under70" && input.outpatientOnly && band.outpatient !== undefined;
  let cap: number;
  let capLabel: string;
  if (outpatient) {
    cap = band.outpatient!;
    capLabel = "外来（通院）だけの月の、ひとりの上限";
  } else if (input.many && manyCap !== undefined) {
    cap = manyCap;
    capLabel = "4か月目から（多数回該当）の上限";
  } else {
    cap = normalCap;
    capLabel = input.age === "under70" ? "1か月の上限" : "1か月の上限（入院を含む・世帯ごと）";
  }
  const windowShare = Math.round(totalMedical * share);
  const pay = Math.min(windowShare, cap);
  return {
    band,
    totalMedical,
    entered,
    share,
    cap,
    capLabel,
    fixed: outpatient || (input.many === true && manyCap !== undefined) || band.threshold === undefined,
    normalCap,
    manyCap,
    windowShare,
    pay,
    over: Math.max(0, windowShare - pay),
    yearly: band.yearly,
    outpatientYearly: outpatient ? band.outpatientYearly : undefined,
  };
}

/** 世帯合算: 69歳までは、1つの医療機関（医科・歯科の入院・外来ごと）の自己負担がこの額以上の分だけを合わせる（協会けんぽの案内） */
export const KOGAKU_SETAI_MIN = 21000;
/** 区分エのうち年収約200万円まで（標準報酬月額15万円以下）と確認できた人の年間の上限。令和9年8月以降に償還払い（厚労省の資料・協会けんぽ） */
export const KOGAKU_LOW_YEARLY = 410000;

/** 円の表示（整数） */
export function yenJa(value: number): string {
  return `${Math.round(value).toLocaleString("ja-JP")}円`;
}

/** 「1,680,000」→「168万円」（年間上限の表示。1万円未満の端数が無い額だけ） */
export function manYen(value: number): string {
  return value % 10000 === 0 ? `${(value / 10000).toLocaleString("ja-JP")}万円` : yenJa(value);
}

/** 例の表の総医療費（公式の平均ではなく、計算の例として置いた額） */
export const KOGAKU_EXAMPLE_TOTALS = [500_000, 1_000_000, 2_000_000] as const;

export type KogakuExampleRow = { band: KogakuBandInfo; pays: number[]; many?: number };

/** 例の表（70歳未満・窓口3割・1回目〜3回目）。ページの数字はすべてここから出す。手で書かない */
export function kogakuExampleTable(): KogakuExampleRow[] {
  return bandsFor("under70").map((band) => ({
    band,
    pays: KOGAKU_EXAMPLE_TOTALS.map((total) => kogaku({ age: "under70", band: band.key, totalMedical: total }).pay),
    many: band.many,
  }));
}
