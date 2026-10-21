"use client";

import { useEffect, useState } from "react";

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

const clock = new Intl.DateTimeFormat("ja-JP", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Tokyo",
});
const monthDay = new Intl.DateTimeFormat("ja-JP", {
  month: "numeric",
  day: "numeric",
  timeZone: "Asia/Tokyo",
});
const full = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Tokyo",
});

const jstDay = (time: number) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(time);

/** 「12分前」「3時間前」「昨日 19:41」「10/17」 */
export function relative(iso: string, now: number): string {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return "";
  const diff = now - time;
  if (diff < MINUTE) return "たった今";
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)}分前`;
  if (diff < 24 * HOUR) return `${Math.floor(diff / HOUR)}時間前`;
  if (jstDay(now - 24 * HOUR) === jstDay(time)) return `昨日 ${clock.format(time)}`;
  return monthDay.format(time);
}

type Props = {
  iso: string;
  className?: string;
};

/**
 * 経過時間で表示する時刻。
 * サイトは数時間おきに静的生成されるので、「何分前か」はビルド時ではなく
 * 読者の端末で計算する。サーバーでは日付を出し、表示後に経過時間へ置き換える。
 */
export default function RelTime({ iso, className }: Props) {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), MINUTE);
    return () => clearInterval(timer);
  }, []);

  const time = Date.parse(iso);
  if (Number.isNaN(time)) return null;

  return (
    <time dateTime={iso} title={full.format(time)} className={className} suppressHydrationWarning>
      {now === null ? monthDay.format(time) : relative(iso, now)}
    </time>
  );
}
