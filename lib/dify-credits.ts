/** 計算欄の入力範囲。Difyのサービス上限・消費率を示す値ではない。 */
export const MAX_DIFY_CREDIT_INPUT = 1_000_000;
export const DIFY_CREDIT_DECIMAL_PLACES = 6;

export type CreditInputError = "format" | "precision" | "range" | "zero";
export type DifyCreditEstimate = {
  status: "incomplete" | "invalid" | "ready";
  runs: number | null;
  remainingError: CreditInputError | null;
  perRunError: CreditInputError | null;
};

type ParsedCredit = { units: bigint | null; error: CreditInputError | null };
const SCALE = 1_000_000n;
const MAX_UNITS = BigInt(MAX_DIFY_CREDIT_INPUT) * SCALE;
const DECIMAL = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

function parseCredit(input: string, allowZero: boolean): ParsedCredit {
  const value = input.trim();
  if (!value) return { units: null, error: null };
  // 桁数を先に制限し、指数・符号・NaN・Infinity・カンマを受け付けない。
  if (value.length > 32 || !DECIMAL.test(value)) return { units: null, error: "format" };
  const [whole = "", fraction = ""] = value.split(".");
  const meaningfulFraction = fraction.replace(/0+$/, "");
  if (meaningfulFraction.length > DIFY_CREDIT_DECIMAL_PLACES) return { units: null, error: "precision" };
  // 浮動小数にせず同じ桁の整数へ。0.3 / 0.1 などを一回少なく数えない。
  const units = BigInt(whole || "0") * SCALE + BigInt(meaningfulFraction.padEnd(DIFY_CREDIT_DECIMAL_PLACES, "0"));
  if (units > MAX_UNITS) return { units: null, error: "range" };
  if (!allowZero && units === 0n) return { units: null, error: "zero" };
  return { units, error: null };
}

/** 同じ処理の消費量が続く場合の切捨て目安。料金・実行成功・無料利用の保証ではない。 */
export function estimateDifyCreditRuns(remainingInput: string, perRunInput: string): DifyCreditEstimate {
  const remaining = parseCredit(remainingInput, true);
  const perRun = parseCredit(perRunInput, false);
  const errors = { remainingError: remaining.error, perRunError: perRun.error };
  if (remaining.error || perRun.error) return { status: "invalid", runs: null, ...errors };
  if (remaining.units === null || perRun.units === null) return { status: "incomplete", runs: null, ...errors };
  // 最大でも100万 / 0.000001 = 1兆で、Numberの安全な整数範囲内。
  return { status: "ready", runs: Number(remaining.units / perRun.units), ...errors };
}
