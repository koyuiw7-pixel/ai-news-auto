"use client";

import { useEffect, useRef, useState } from "react";

/**
 * 2つ目以降の行（PrRow）の小さなバナー。画像が無い・読み込めなかった（広告ブロック等）ときは、
 * 空の白い枠を残さず枠ごと消す（2026-11-11 オーナー指摘: au PAY ふるさと納税の行に空の枠）。
 * 幅は固定なので、読み込めたときは画面がずれない。
 */
export default function RowThumb({ src, className = "" }: { src: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLImageElement>(null);
  useEffect(() => {
    const img = ref.current;
    // 水和より前に失敗していた場合（onError を取りこぼす）
    if (img && img.complete && img.naturalWidth === 0) setFailed(true);
  }, []);
  if (failed) return null;
  return (
    <span className={`relative block aspect-[6/5] shrink-0 overflow-hidden rounded-lg border border-line bg-white ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img ref={ref} src={src} alt="" width={300} height={250} loading="lazy" decoding="async" fetchPriority="low" onError={() => setFailed(true)} className="absolute inset-0 h-full w-full object-contain" />
    </span>
  );
}
