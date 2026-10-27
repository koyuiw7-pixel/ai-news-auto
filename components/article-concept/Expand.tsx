"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

type Props = {
  minute: ReactNode;
  full: ReactNode;
  minuteLabel: string;
  fullLabel: string;
};

/**
 * 「もっと詳しく」。押すたびに 10秒版 → 1分版 → 全文 と、その場で文章が伸びる。
 * ページ遷移・タブ・複数のボタンは使わない。操作はこの1つだけ。
 * 続報の線（#update-*）から飛んできたときは全文まで開いてからその章へ移る。
 */
export default function Expand({ minute, full, minuteLabel, fullLabel }: Props) {
  const [level, setLevel] = useState(0);
  // 続報の線から飛ぶときは、伸びる動きを省いて一度に開く（動いている途中だと行き先がずれる）
  const [instant, setInstant] = useState(false);
  const minuteRef = useRef<HTMLDivElement>(null);
  const fullRef = useRef<HTMLDivElement>(null);

  const reveal = useCallback((next: number) => {
    setLevel((current) => Math.max(current, next));
    // 開いた段の先頭へフォーカスだけ移す（画面は動かさない）
    requestAnimationFrame(() => (next === 1 ? minuteRef : fullRef).current?.focus({ preventScroll: true }));
  }, []);

  useEffect(() => {
    const jump = () => {
      const id = decodeURIComponent(location.hash.slice(1));
      const target = id ? fullRef.current?.querySelector<HTMLElement>(`[id="${CSS.escape(id)}"]`) : null;
      if (!target) return;
      setInstant(true);
      setLevel(2);
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
          setInstant(false);
        }),
      );
    };
    jump();
    addEventListener("hashchange", jump);
    return () => removeEventListener("hashchange", jump);
  }, []);

  return (
    <div className="cx-expand" data-level={level} data-instant={instant || undefined}>
      <div className="cx-reveal" data-open={level >= 1} inert={level < 1}>
        <div className="cx-reveal-inner">
          <div ref={minuteRef} tabIndex={-1} className="cx-stage cx-stage-minute" aria-label="1分で読める版">
            {minute}
          </div>
        </div>
      </div>
      <div className="cx-reveal" data-open={level >= 2} inert={level < 2}>
        <div className="cx-reveal-inner">
          <div ref={fullRef} tabIndex={-1} className="cx-stage cx-stage-full" aria-label="全文">
            {full}
          </div>
        </div>
      </div>
      {level < 2 && (
        <button type="button" className="cx-more" onClick={() => reveal(level + 1)} aria-expanded={false}>
          <span className="cx-more-text">もっと詳しく</span>
          <span className="cx-more-rule" aria-hidden />
          <span className="cx-more-time">{level === 0 ? minuteLabel : fullLabel}</span>
          <svg className="cx-more-arrow" viewBox="0 0 16 16" aria-hidden>
            <path d="M8 2.5v10M3.5 8.5 8 13l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </div>
  );
}
