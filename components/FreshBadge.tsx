"use client";

import { useEffect, useState } from "react";
import { LATEST_MS } from "@/lib/live-line";

/**
 * 「新着」の札。載せてから24時間以内のときだけ出す（2026-11-11 読者目線レビュー 11位: 古い記事に「新着」「最新」が付いていた）。
 * ページは静的に作って長くキャッシュするので、最初は描いた時刻（renderedAt）で決め、表示後に閲覧時刻で当て直す（components/LiveLine.tsx と同じ）
 */
export default function FreshBadge({ iso, renderedAt, label = "新着", className = "" }: { iso: string; renderedAt: number; label?: string; className?: string }) {
  const [now, setNow] = useState(renderedAt);
  useEffect(() => setNow(Date.now()), []);
  const t = Date.parse(iso);
  if (!Number.isFinite(t) || now - t >= LATEST_MS) return null;
  return <span className={className}>{label}</span>;
}
