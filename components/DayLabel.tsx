"use client";

import { useEffect, useState } from "react";

const label = new Intl.DateTimeFormat("ja-JP", {
  month: "long",
  day: "numeric",
  weekday: "short",
  timeZone: "Asia/Tokyo",
});
const jstDay = (time: number) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(time);

/**
 * タイムラインの日付見出し。「今日」「昨日」は読者の端末の日付で判定する
 * （静的生成のため、ビルド時に決めると翌日にずれる）。
 * @param day JSTの日付（YYYY-MM-DD）
 */
export default function DayLabel({ day }: { day: string }) {
  const [relativeDay, setRelativeDay] = useState<string | null>(null);

  useEffect(() => {
    const now = Date.now();
    if (jstDay(now) === day) setRelativeDay("今日");
    else if (jstDay(now - 86_400_000) === day) setRelativeDay("昨日");
  }, [day]);

  const date = label.format(Date.parse(`${day}T12:00:00+09:00`));

  return (
    <span suppressHydrationWarning>
      {relativeDay && <span className="mr-2 text-ink">{relativeDay}</span>}
      <span className={relativeDay ? "text-muted" : "text-ink"}>{date}</span>
    </span>
  );
}
