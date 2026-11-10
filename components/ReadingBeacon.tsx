"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { INFLOW_BOT_UA, INTERNAL_PARAM, INTERNAL_STORAGE_KEY, classifyInflow, isArticleKey, pageKey } from "@/lib/inflow";
import { depthBucket, normalizeAdPositions, timeBucket, type ExitZone, type ReadingSource } from "@/lib/reading";

/** そのタブで最初に開いたページか（2ページ目からはサイト内の移動として "internal"） */
let firstPage = true;

/**
 * 記事を「どこまで読んだか・どれだけ見ていたか・次にどこを押したか」を1ページにつき1件だけ送る（cloudflare/reading.ts の POST /api/aff/read）。
 * 決まりは lib/reading.ts。画面の見た目は何も変えない。計測が失敗しても読む・押す動きは止めない。
 * 送らないもの: 自動ブラウザ・ロボット、?_internal=1 で開いたブラウザ、Do Not Track / GPC のブラウザ、記事以外のページ。
 */
export default function ReadingBeacon() {
  const pathname = usePathname();
  useEffect(() => {
    if (!pathname) return;
    const isFirst = firstPage;
    firstPage = false;
    try {
      const slug = pageKey(pathname);
      if (!slug || !isArticleKey(slug)) return;
      if (navigator.webdriver || INFLOW_BOT_UA.test(navigator.userAgent) || typeof navigator.sendBeacon !== "function") return;
      if (navigator.doNotTrack === "1" || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl) return;
      if (new URLSearchParams(location.search).get(INTERNAL_PARAM) === "1") return;
      try { if (localStorage.getItem(INTERNAL_STORAGE_KEY) === "1") return; } catch { /* storage が使えなくても続ける */ }
      const inflow = isFirst ? classifyInflow(location.search, document.referrer, location.origin) : null;
      const source: ReadingSource = inflow?.source ?? "internal";
      return installReading(slug, source);
    } catch {
      return;
    }
  }, [pathname]);
  return null;
}

/** 実ブラウザ・本番への送信なしで回帰検証できる単位（components/ReadingBeacon.test.ts） */
export function installReading(slug: string, source: ReadingSource, send = (body: string) => navigator.sendBeacon("/api/aff/read", body)) {
  let visibleMs = 0;
  let visibleSince = document.visibilityState === "visible" ? performance.now() : -1;
  let maxRatio = 0;
  let nextRead = false;
  const seen: string[] = [];
  let exit: ExitZone = "";
  let lastSent = "";

  // サイト内の移動の直後は、前のページのスクロール位置が残っている（Next.js が先頭へ戻す前）。少し待ってから測り始める
  let ready = false;
  const measure = () => {
    if (!ready) return;
    const main = document.querySelector("main");
    const bottom = main ? main.getBoundingClientRect().bottom + window.scrollY : document.documentElement.scrollHeight;
    if (bottom > 0) maxRatio = Math.max(maxRatio, (window.scrollY + window.innerHeight) / bottom);
  };
  let frame = 0;
  const onScroll = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; measure(); });
  };

  const flush = (remeasure = true) => {
    const now = performance.now();
    const ms = visibleMs + (visibleSince >= 0 ? now - visibleSince : 0);
    // 画面切り替えの後片付けでは、もう次のページが描かれているので測り直さない
    if (remeasure) measure();
    const body = JSON.stringify({ p: slug, s: source, d: depthBucket(maxRatio), t: timeBucket(ms / 1000), n: nextRead, a: normalizeAdPositions(seen), x: exit });
    // 前回と同じ中身なら送らない（Worker は同じ人・同じ記事の記録を最新で上書きする）
    if (body === lastSent) return;
    try { if (send(body)) lastSent = body; } catch { /* 計測は読む動きを止めない */ }
  };

  const onVisibility = () => {
    if (document.visibilityState === "visible") {
      if (visibleSince < 0) visibleSince = performance.now();
      return;
    }
    if (visibleSince >= 0) { visibleMs += performance.now() - visibleSince; visibleSince = -1; }
    flush();
  };

  const onClick = (event: MouseEvent) => {
    if (!event.isTrusted || event.button > 1) return;
    const link = (event.target as Element | null)?.closest?.("a") as HTMLAnchorElement | null;
    if (!link || link.origin !== location.origin || /\bsponsored\b/.test(link.rel) || link.pathname === location.pathname) return;
    exit = link.closest("header") ? "header"
      : link.closest('[data-read-zone="story"]') ? "story"
      : link.closest("[data-money-link]") ? "money"
      : link.closest('section[aria-labelledby="next-read-heading"]') ? "nextread"
      : link.closest("footer") ? "footer"
      : link.closest("aside") ? "aside"
      : "body";
    // 押した時点（まだこのページが表示されている）で送る
    flush();
  };

  const io = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting || document.visibilityState !== "visible") continue;
      const el = entry.target as HTMLElement;
      const pos = el.getAttribute("data-aff-pos");
      if (pos) { if (!seen.includes(pos)) seen.push(pos); } else nextRead = true;
      io?.unobserve(el);
    }
  }, { threshold: 0.5 }) : null;
  const observe = () => {
    if (!io) return;
    document.querySelectorAll("[data-aff-pos], section[aria-labelledby=\"next-read-heading\"]").forEach((el) => io.observe(el));
  };
  const start = setTimeout(() => { ready = true; measure(); observe(); }, 600);
  // 後から描かれる枠（遅れて出る PR・関連記事）も拾う
  const late = setTimeout(observe, 3000);

  window.addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("visibilitychange", onVisibility);
  const onPageHide = () => flush();
  window.addEventListener("pagehide", onPageHide);
  document.addEventListener("click", onClick, { capture: true, passive: true });
  document.addEventListener("auxclick", onClick, { capture: true, passive: true });

  return () => {
    // サイト内で次のページへ移るとき（Next.js の画面切り替えはページを離れないので、ここで送る）
    flush(false);
    clearTimeout(start);
    clearTimeout(late);
    if (frame) cancelAnimationFrame(frame);
    io?.disconnect();
    window.removeEventListener("scroll", onScroll);
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("pagehide", onPageHide);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("auxclick", onClick, true);
  };
}
