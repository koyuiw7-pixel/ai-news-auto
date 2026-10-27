/** 金額の表示（サーバー・クライアント共通。依存なし） */
export function formatMoney(value: number, currency: "USD" | "JPY"): string {
  if (currency === "JPY") return `${Math.round(value).toLocaleString("ja-JP")}円`;
  // $0.042 は3桁、$0.05・$0.10・$2.50 は2桁、$20 は整数
  const min = value === 0 || (value >= 1 && value % 1 === 0) ? 0 : 2;
  const max = value > 0 && value < 0.1 ? 3 : 2;
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: min, maximumFractionDigits: Math.max(min, max) })}`;
}

/** 円の概算（「約1,500円」） */
export function formatYen(value: number): string {
  if (value < 1) return "1円未満";
  if (value < 100) return `約${Math.round(value)}円`;
  return `約${(Math.round(value / 10) * 10).toLocaleString("ja-JP")}円`;
}
