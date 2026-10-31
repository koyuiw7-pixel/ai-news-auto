/** 期限つき商品は、時刻を確認できない間や日時が不正なときは表示しない。 */
export function offerIsActive(activeUntil: string | undefined, now: number | null): boolean {
  if (!activeUntil) return true;
  if (now === null || !Number.isFinite(now)) return false;
  const end = Date.parse(activeUntil);
  return Number.isFinite(end) && now < end;
}

export function nextOfferExpiry(values: (string | undefined)[], now: number): number | undefined {
  return values.map((value) => Date.parse(value ?? ""))
    .filter((time) => Number.isFinite(time) && time > now)
    .sort((a, b) => a - b)[0];
}
