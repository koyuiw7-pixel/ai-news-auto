"use client";

import { useEffect } from "react";
import { BOT_UA } from "@/lib/revenue-funnel";

/**
 * 提携リンク（rel に sponsored を含む a）の「人による」クリックを自前で数える。
 * ASP のクリック数にはクローラーや自動ブラウザが混ざるので、実数と見比べるため。
 * 個人を特定する情報は送らない（送るのは 提携先の ID・ページのパス・置き場所 だけ）。受け口は cloudflare/aff.ts
 */

/** 提携先の ID（A8 は a8mat、それ以外はドメイン） */
function programOf(href: string): string {
  try {
    const url = new URL(href);
    const a8mat = url.searchParams.get("a8mat");
    // a8mat の「+」は URLSearchParams で空白に化けるので戻す
    if (a8mat) return a8mat.replace(/ /g, "+").slice(0, 60);
    if (/(^|\.)afl\.rakuten\.co\.jp$/.test(url.hostname)) return "rakuten";
    if (/amazon\.|amzn\.to$/.test(url.hostname)) return "amazon";
    return url.hostname.slice(0, 60);
  } catch {
    return "unknown";
  }
}

export default function AffClickTracker() {
  useEffect(() => {
    if (navigator.webdriver || BOT_UA.test(navigator.userAgent) || typeof navigator.sendBeacon !== "function") return;
    const onClick = (event: MouseEvent) => {
      // 左クリックと中クリック（新しいタブ）だけ。スクリプトが起こしたクリックは数えない
      if (!event.isTrusted || event.button > 1) return;
      const link = (event.target as Element | null)?.closest?.('a[rel~="sponsored"]') as HTMLAnchorElement | null;
      if (!link?.href) return;
      const rank = link.getAttribute("data-aff-rank");
      const pos = link.closest("[data-aff-pos]")?.getAttribute("data-aff-pos") || "other";
      const body = JSON.stringify({ p: programOf(link.href), path: location.pathname, pos: rank ? `${pos}-${rank}` : pos });
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
