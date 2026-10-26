"use client";

import { useEffect, useState } from "react";

const FRESH_MS = 3 * 60 * 60 * 1000;

/**
 * 「LIVE」は本当に新しいとき（最終更新から3時間以内）だけ出す。
 * 古いのに LIVE と出すと、すぐ横の「◯時間前」と食い違って、かえって遅く見えるため。
 */
export default function LiveBadge({ updatedAt }: { updatedAt?: string }) {
  const [fresh, setFresh] = useState(false);
  useEffect(() => {
    if (updatedAt) setFresh(Date.now() - Date.parse(updatedAt) < FRESH_MS);
  }, [updatedAt]);
  if (!fresh) return null;
  return (
    <>
      <span className="relative flex size-2" aria-hidden>
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-live opacity-60 motion-reduce:hidden" />
        <span className="relative inline-flex size-2 rounded-full bg-live" />
      </span>
      <span className="font-bold tracking-wider text-live">LIVE</span>
    </>
  );
}
