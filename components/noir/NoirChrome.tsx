"use client";

import { useEffect } from "react";

/**
 * ノワールの記事の動き（components/noir/NoirArticle.tsx）。
 * 上の帯（表紙の途中からすりガラス→表紙を過ぎると白）・読んだ量の赤い線・表紙の写真のゆっくりした動き・読み進めると現れる段落。
 * 動きを減らす設定の端末では、写真を動かさず、段落もはじめから出しておく。どれも位置ではなく見た目だけを変える（下の物が動かない）
 */
export default function NoirChrome({ fontHref }: { fontHref: string }) {
  useEffect(() => {
    const root = document.documentElement;
    // サイト内の移動で開いたときは、ページの中のスクリプト（NoirFonts）が動かないので、ここで書体を足す
    // 別のノワールの記事へ移ったときは、その記事の文字の版に替える
    const current = document.getElementById("nr-fonts") as HTMLLinkElement | null;
    if (!current) {
      const link = document.createElement("link");
      link.id = "nr-fonts";
      link.rel = "stylesheet";
      link.href = fontHref;
      document.head.appendChild(link);
    } else if (current.href !== fontHref) {
      current.href = fontHref;
    }
    root.classList.add("js-noir");
    const top = document.getElementById("nr-top");
    const bar = document.getElementById("nr-bar");
    const img = document.getElementById("nr-img");
    const hero = document.getElementById("nr-hero");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const update = () => {
      frame = 0;
      const y = window.scrollY;
      const h = root.scrollHeight - window.innerHeight;
      const edge = (hero?.offsetHeight ?? 400) - 60;
      top?.classList.toggle("glass", y > 30 && y <= edge);
      top?.classList.toggle("solid", y > edge);
      if (bar) bar.style.transform = `scaleX(${h > 0 ? Math.min(1, y / h) : 0})`;
      if (img && !reduce && y < 900) img.style.transform = `translateY(${y * 0.35}px) scale(${1 + y / 3000})`;
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    update();

    let io: IntersectionObserver | undefined;
    if (!reduce && "IntersectionObserver" in window) {
      const els = [...document.querySelectorAll<HTMLElement>(".noir .rv, .noir [data-rv]")];
      els.forEach((el) => {
        if (el.getBoundingClientRect().top > window.innerHeight * 0.95) el.classList.add("pre");
      });
      io = new IntersectionObserver(
        (entries) =>
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.remove("pre");
              io?.unobserve(entry.target);
            }
          }),
        { rootMargin: "0px 0px -8% 0px" },
      );
      els.forEach((el) => io?.observe(el));
    }
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
      io?.disconnect();
      document.querySelectorAll(".noir .pre").forEach((el) => el.classList.remove("pre"));
      root.classList.remove("js-noir");
    };
  }, [fontHref]);
  return null;
}
