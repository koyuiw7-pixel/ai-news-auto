"use client";

import { useEffect, useState } from "react";
import { nextOfferExpiry, offerIsActive } from "@/lib/offer-time";

/** 期限つき商品は表示中だけ元の計測画像を読み、期限後は読み込まない。 */
export default function TimedPixels({ pixels, enabled }: { pixels: { url: string; activeUntil: string }[]; enabled: boolean }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    let timer: number | undefined;
    const tick = () => {
      if (timer) window.clearTimeout(timer);
      const current = Date.now();
      setNow(current);
      const next = nextOfferExpiry(pixels.map((pixel) => pixel.activeUntil), current);
      if (next) timer = window.setTimeout(tick, Math.min(next - current + 50, 2_147_483_647));
    };
    tick();
    document.addEventListener("visibilitychange", tick);
    return () => { if (timer) window.clearTimeout(timer); document.removeEventListener("visibilitychange", tick); };
  }, [pixels]);
  if (!enabled || now === null) return null;
  const active = pixels.filter((pixel) => offerIsActive(pixel.activeUntil, now)).map((pixel) => pixel.url);
  return <>{active.map((pixel) => (
    // 計測用URLと画像属性は既存のPixelsと同じ。外部通信は検証時に遮断する。
    // eslint-disable-next-line @next/next/no-img-element
    <img key={pixel} src={pixel} width={1} height={1} alt="" loading="lazy" fetchPriority="low" className="absolute size-px opacity-0" />
  ))}</>;
}
