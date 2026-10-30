"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { BOT_UA, CHOICES, FUNNEL, GUIDE_PATH, SOURCES, sourceOf, type Source, type Stage } from "@/lib/revenue-funnel";

const STORAGE_KEY = "saisoku-source-v1";
const MAX_AGE = 30 * 60_000;

/** タブ内の流入元の分類だけを30分保持。識別子・参照元の原文・検索語は保存しない。 */
function source(): Source {
  const current = sourceOf(location.search, document.referrer, location.origin);
  try {
    const cached = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if ((current === "direct" || current === "internal") && cached && Date.now() - cached.at >= 0 && Date.now() - cached.at < MAX_AGE && SOURCES.includes(cached.source)) return cached.source;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ source: current, at: Date.now() }));
  } catch { /* storage may be disabled; measurement still works without it */ }
  return current;
}

export default function RevenueFunnelTracker() {
  const pathname = usePathname();
  const channelRef = useRef<Source | null>(null);
  useEffect(() => {
    if (!pathname || navigator.webdriver || BOT_UA.test(navigator.userAgent) || navigator.doNotTrack === "1" ||
      (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl || typeof navigator.sendBeacon !== "function") return;
    const channel = channelRef.current ?? (channelRef.current = source());
    const sent = new Set<string>();
    const send = (stage: Stage, choice = "", pos = "other") => {
      const key = `${stage}:${choice}`;
      if (sent.has(key)) return;
      // 失敗しても表示・リンク遷移を止めない。クエリ文字列やリンク先URLは送らない。
      try {
        if (navigator.sendBeacon("/api/aff/event", JSON.stringify({ funnel: FUNNEL, stage, path: pathname, source: channel, choice, pos }))) sent.add(key);
      } catch { /* analytics must never interrupt reading or navigation */ }
    };
    let timer: ReturnType<typeof setTimeout> | undefined;
    const visible = () => {
      clearTimeout(timer);
      if (document.visibilityState !== "visible") return;
      timer = setTimeout(() => {
        if (pathname === "/guides") send("entry_view", "", "guide-list");
        if (pathname === GUIDE_PATH) send("guide_view");
      }, 1000);
    };
    visible();
    document.addEventListener("visibilitychange", visible);
    const click = (event: MouseEvent) => {
      if (!event.isTrusted || event.button > 1) return;
      const link = (event.target as Element | null)?.closest?.("a") as HTMLAnchorElement | null;
      if (!link) return;
      if (pathname !== GUIDE_PATH && link.origin === location.origin && link.pathname === GUIDE_PATH) {
        send("guide_click", "", link.closest("[data-funnel-pos]")?.getAttribute("data-funnel-pos") || "other");
      }
      const choice = link.getAttribute("data-funnel-choice");
      if (pathname === GUIDE_PATH && choice && CHOICES.includes(choice as typeof CHOICES[number])) {
        send("choice_click", choice, link.closest("[data-aff-pos]")?.getAttribute("data-aff-pos") || "other");
      }
    };
    document.addEventListener("click", click, { capture: true, passive: true });
    document.addEventListener("auxclick", click, { capture: true, passive: true });
    const heading = pathname === GUIDE_PATH ? document.getElementById("table-heading") : null;
    const observer = heading && typeof IntersectionObserver !== "undefined" ? new IntersectionObserver((entries) => {
      if (document.visibilityState === "visible" && entries.some((entry) => entry.isIntersecting)) send("comparison_view");
    }, { threshold: 0.5 }) : null;
    if (heading) observer?.observe(heading);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visible);
      document.removeEventListener("click", click, true);
      document.removeEventListener("auxclick", click, true);
      observer?.disconnect();
    };
  }, [pathname]);
  return null;
}
