/** 特集（lib/flagship.ts）の日付の小さな計算。ブラウザの部品からも使うので、事実の JSON を読み込まない別のファイルにする */

/** 2026-11-28 → 2026年11月28日 */
export function dateJa(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${y}年${m}月${d}日`;
}

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];

/** 出生日（YYYY-MM-DD）→ 認定請求の期限（次の日から数えて15日目）。日付の計算は UTC で行い、端末の時刻帯でずれないようにする */
export function birthDeadline(iso: string): { iso: string; label: string } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 15));
  if (Number.isNaN(d.getTime())) return null;
  const y = d.getUTCFullYear();
  const mo = d.getUTCMonth() + 1;
  const day = d.getUTCDate();
  return { iso: `${y}-${String(mo).padStart(2, "0")}-${String(day).padStart(2, "0")}`, label: `${y}年${mo}月${day}日（${WEEK[d.getUTCDay()]}）` };
}

