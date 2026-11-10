"use client";

import { useEffect } from "react";
import { programOf } from "@/lib/aff-program";
import { BOT_UA } from "@/lib/revenue-funnel";

/**
 * 提携リンク（rel に sponsored を含む a）の「人による」クリックを自前で数える。
 * ASP のクリック数にはクローラーや自動ブラウザが混ざるので、実数と見比べるため。
 * 個人を特定する情報は送らない（送るのは 提携先の ID・ページのパス・置き場所 だけ）。受け口は cloudflare/aff.ts
 */

export default function AffClickTracker() {
  useEffect(() => {
    if (navigator.webdriver || BOT_UA.test(navigator.userAgent) || typeof navigator.sendBeacon !== "function") return;
    const onClick = (event: MouseEvent) => {
      // 左クリックと中クリック（新しいタブ）だけ。スクリプトが起こしたクリックは数えない
      if (!event.isTrusted || event.button > 1) return;
      const link = (event.target as Element | null)?.closest?.('a[rel~="sponsored"]') as HTMLAnchorElement | null;
      if (!link?.href) return;
      const rank = link.getAttribute("data-aff-rank");
      const box = link.closest("[data-aff-pos]");
      const pos = box?.getAttribute("data-aff-pos") || "other";
      // PR の囲み（data-ad-ab）は、ボタンの色の A/B（<html data-adv>。app/layout.tsx）もいっしょに送る（cloudflare/aff.ts の byVariant）
      const variant = box?.hasAttribute("data-ad-ab") ? document.documentElement.getAttribute("data-adv") : null;
      // 得のカードの A/B（lib/ad-ab.ts。台帳 W41）: 押したリンクのある arm（data-ab-arm）。cloudflare/aff.ts の byArm
      const arm = link.closest("[data-ab-arm]")?.getAttribute("data-ab-arm");
      const body = JSON.stringify({
        p: programOf(link.href),
        path: location.pathname,
        pos: rank ? `${pos}-${rank}` : pos,
        ...(variant === "a" || variant === "b" ? { ab: variant } : {}),
        ...(arm === "1" || arm === "2" ? { arm } : {}),
      });
      navigator.sendBeacon("/api/aff/click", body);
    };
    document.addEventListener("click", onClick, { capture: true, passive: true });
    document.addEventListener("auxclick", onClick, { capture: true, passive: true });
    return () => {
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("auxclick", onClick, true);
    };
  }, []);
  return null;
}
