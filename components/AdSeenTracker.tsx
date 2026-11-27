"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { BOT_UA } from "@/lib/revenue-funnel";
import { INTERNAL_PARAM, INTERNAL_STORAGE_KEY } from "@/lib/inflow";
import { AD_SEEN_MS, AD_SEEN_RATIO, AD_SLOT_EVENT, adSeenBody } from "@/lib/ad-seen";

/**
 * 広告の囲み（data-aff-pos のある枠）を「人が見た」数を数える（2026-11-27。広告の押した割合＝人のクリック ÷ 見た人。lib/ad-seen.ts）。
 * 枠が画面に半分以上入った状態が1秒続いたら、そのページの表示につき枠ごとに1回だけ POST /api/aff/seen（cloudflare/aff.ts）。
 * 送るのは ページのパス（クエリ文字列なし）・置き場所・A/B の組（data-adv・data-abc）だけ。識別子は送らない。
 * 送らないもの: 自動ブラウザ・ロボット、Do Not Track / GPC のブラウザ、?_internal=1 で開いたブラウザ（components/ReadingBeacon.tsx と同じ）。
 * 計算ツールの結果の下の A/B は、選ばれた方の枠だけがページにある（components/ToolAdSlot.tsx）。画面の見た目は何も変えない。
 */
export default function AdSeenTracker() {
  const pathname = usePathname();
  useEffect(() => {
    if (!pathname) return;
    try {
      if (navigator.webdriver || BOT_UA.test(navigator.userAgent) || typeof navigator.sendBeacon !== "function") return;
      if (navigator.doNotTrack === "1" || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl) return;
      if (new URLSearchParams(location.search).get(INTERNAL_PARAM) === "1") return;
      try { if (localStorage.getItem(INTERNAL_STORAGE_KEY) === "1") return; } catch { /* storage が使えなくても続ける */ }
      return installAdSeen(pathname);
    } catch {
      return;
    }
  }, [pathname]);
  return null;
}

/** 実ブラウザ・本番への送信なしで回帰検証できる単位（components/AdSeenTracker.test.ts） */
export function installAdSeen(pathname: string, send = (body: string) => navigator.sendBeacon("/api/aff/seen", body)) {
  const sent = new Set<string>();
  const timers = new Map<Element, ReturnType<typeof setTimeout>>();
  const visible = new Set<Element>();
  const attr = (name: string) => {
    try { return document.documentElement.getAttribute(name); } catch { return null; }
  };
  const fire = (el: Element) => {
    timers.delete(el);
    if (!visible.has(el) || document.visibilityState !== "visible") return;
    const pos = el.getAttribute("data-aff-pos") || "";
    if (sent.has(pos)) return;
    const body = adSeenBody({
      path: pathname,
      pos,
      ab: el.hasAttribute("data-ad-ab") ? attr("data-adv") : null,
      arm: typeof el.querySelector === "function" && el.querySelector("[data-ab-arm]") ? attr("data-abc") : null,
    });
    if (!body) return;
    sent.add(pos);
    try { send(body); } catch { /* 計測は読む・押す動きを止めない */ }
  };
  const arm = (el: Element) => {
    if (timers.has(el) || document.visibilityState !== "visible") return;
    timers.set(el, setTimeout(() => fire(el), AD_SEEN_MS));
  };
  const disarm = (el: Element) => {
    const t = timers.get(el);
    if (t !== undefined) clearTimeout(t);
    timers.delete(el);
  };
  const io = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const el = entry.target;
      if (entry.isIntersecting && entry.intersectionRatio >= AD_SEEN_RATIO) {
        visible.add(el);
        arm(el);
      } else {
        visible.delete(el);
        disarm(el);
      }
    }
  }, { threshold: [0, AD_SEEN_RATIO] }) : null;
  const watched = new Set<Element>();
  const observe = () => {
    if (!io) return;
    document.querySelectorAll("[data-aff-pos]").forEach((el) => {
      if (watched.has(el)) return;
      watched.add(el);
      io.observe(el);
    });
  };
  // タブを隠したら待ちを止め、戻ったら見えている枠から1秒を数え直す
  const onVisibility = () => {
    if (document.visibilityState !== "visible") { for (const el of [...timers.keys()]) disarm(el); return; }
    for (const el of visible) arm(el);
  };
  observe();
  // 後から描かれる枠（遅れて出る PR）も拾う
  const late = setTimeout(observe, 3000);
  // 計算ツールの結果の下の PR（components/ToolAdSlot.tsx）は描いたときに合図が来る
  const win = typeof window !== "undefined" ? window : undefined;
  win?.addEventListener(AD_SLOT_EVENT, observe);
  document.addEventListener("visibilitychange", onVisibility);
  return () => {
    clearTimeout(late);
    for (const el of [...timers.keys()]) disarm(el);
    io?.disconnect();
    win?.removeEventListener(AD_SLOT_EVENT, observe);
    document.removeEventListener("visibilitychange", onVisibility);
  };
}
