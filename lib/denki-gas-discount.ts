/**
 * 冬の電気・ガス料金支援の「うちの場合」の計算（/tools/denki-gas-discount と、電気・ガス料金支援の記事の中の計算機）。サーバー・ブラウザ共通、依存なし。
 * 式は tests/test_denki_gas_discount.cjs で確かめている。2026-11-26 に公式ページで確認。
 *
 * 出典: 経済産業省 資源エネルギー庁「電気・ガス料金支援」特設サイト（https://denkigas-gekihenkanwa.go.jp/）
 *  - 対象期間: 2026年12月使用分〜2027年2月使用分。「12月使用分」は原則、12月中の検針日から1月中の検針日までの使用分。
 *  - 値引き単価: 2026年12月使用分 電気（低圧）1.0円/kWh・電気（高圧）0.5円/kWh・都市ガス 4.0円/㎥。
 *    2027年1月・2月使用分 電気（低圧）4.5円/kWh・電気（高圧）2.3円/kWh・都市ガス 18.0円/㎥。
 *  - 値引き額＝値引き単価×月々の使用量。申請は不要。参加している電力・ガス会社の請求で反映。プロパンガス（LPガス）は対象外。
 *  - 特設サイトの試算は、1月・2月の使用量を12月の約2割増しで入れている（読者が書き換えられる）。この計算機も同じにする。
 * 家庭は低圧。高圧（工場・ビルなど）は注記だけで、入力には出さない。
 */

export const DENKI_GAS_SOURCE = { href: "https://denkigas-gekihenkanwa.go.jp/", label: "経済産業省 資源エネルギー庁「電気・ガス料金支援」特設サイト" } as const;

export type DenkiGasMonthKey = "dec" | "jan" | "feb";
export type DenkiGasMonth = { key: DenkiGasMonthKey; label: string; electricity: number; electricityHigh: number; gas: number };

/** 月ごとの値引き単価（円。電気は1kWhあたり、都市ガスは1㎥あたり） */
export const DENKI_GAS_MONTHS: readonly DenkiGasMonth[] = [
  { key: "dec", label: "2026年12月使用分", electricity: 1.0, electricityHigh: 0.5, gas: 4.0 },
  { key: "jan", label: "2027年1月使用分", electricity: 4.5, electricityHigh: 2.3, gas: 18.0 },
  { key: "feb", label: "2027年2月使用分", electricity: 4.5, electricityHigh: 2.3, gas: 18.0 },
];

/** 1月・2月の使用量の初期値＝12月×1.2（特設サイトの試算と同じ「約2割増し」） */
export const WINTER_RATIO = 1.2;
export const DENKI_GAS_DEFAULT = { electricity: 260, gas: 30 } as const;

/** 12月の使用量 → 1月・2月の初期値（四捨五入） */
export function winterUsage(december: number): number {
  return Math.round(Math.max(0, december) * WINTER_RATIO);
}

export type DenkiGasUsage = { electricity: number; gas: number };
export type DenkiGasInput = { dec: DenkiGasUsage; jan: DenkiGasUsage; feb: DenkiGasUsage; propane?: boolean };
export type DenkiGasMonthResult = { key: DenkiGasMonthKey; label: string; electricity: number; gas: number; total: number; usage: DenkiGasUsage };
export type DenkiGasResult = { months: DenkiGasMonthResult[]; electricity: number; gas: number; total: number };

/** 浮動小数の誤差を消す（4.5円×kWh は 0.5円単位になる。請求での端数の扱いは会社ごとに異なる） */
const tidy = (value: number) => Math.round(value * 100) / 100;
const safe = (value: number) => (Number.isFinite(value) && value > 0 ? value : 0);

/** 値引き額＝値引き単価×月々の使用量（特設サイトの説明どおり）。プロパンガスの家庭はガスを0にする */
export function denkiGasDiscount(input: DenkiGasInput): DenkiGasResult {
  const months = DENKI_GAS_MONTHS.map((m) => {
    const usage = input[m.key];
    const kwh = safe(usage.electricity);
    const m3 = input.propane ? 0 : safe(usage.gas);
    const electricity = tidy(m.electricity * kwh);
    const gas = tidy(m.gas * m3);
    return { key: m.key, label: m.label, electricity, gas, total: tidy(electricity + gas), usage: { electricity: kwh, gas: m3 } };
  });
  const electricity = tidy(months.reduce((s, m) => s + m.electricity, 0));
  const gas = tidy(months.reduce((s, m) => s + m.gas, 0));
  return { months, electricity, gas, total: tidy(electricity + gas) };
}

/** 12月の使用量だけから、1月・2月を12月×1.2で入れた入力を作る */
export function inputFromDecember(electricity: number, gas: number, propane = false): DenkiGasInput {
  return {
    dec: { electricity, gas },
    jan: { electricity: winterUsage(electricity), gas: winterUsage(gas) },
    feb: { electricity: winterUsage(electricity), gas: winterUsage(gas) },
    propane,
  };
}

/** 円の表示（0.5円のような端数があれば小数第1位まで） */
export function yenDecimal(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded.toLocaleString("ja-JP", { maximumFractionDigits: 1 })}円`;
}

/** 単価の表示（1.0円・4.5円・18.0円のように小数第1位まで） */
export function unitPrice(value: number): string {
  return `${value.toFixed(1)}円`;
}

/** 例の前提（公式の平均ではなく、計算の例として置いた使用量） */
export const DENKI_GAS_EXAMPLES: { label: string; electricity: number; gas: number }[] = [
  { label: "一人暮らし（例）", electricity: 150, gas: 15 },
  { label: "2人暮らし（例）", electricity: 250, gas: 25 },
  { label: "4人家族（例）", electricity: 400, gas: 40 },
];

export type DenkiGasExampleRow = {
  label: string;
  decElectricity: number;
  decGas: number;
  winterElectricity: number;
  winterGas: number;
  dec: number;
  jan: number;
  feb: number;
  total: number;
};

/** 例の表（ページの数字はすべてここから出す。手で書かない） */
export function denkiGasExampleTable(): DenkiGasExampleRow[] {
  return DENKI_GAS_EXAMPLES.map((ex) => {
    const r = denkiGasDiscount(inputFromDecember(ex.electricity, ex.gas));
    return {
      label: ex.label,
      decElectricity: ex.electricity,
      decGas: ex.gas,
      winterElectricity: winterUsage(ex.electricity),
      winterGas: winterUsage(ex.gas),
      dec: r.months[0].total,
      jan: r.months[1].total,
      feb: r.months[2].total,
      total: r.total,
    };
  });
}
