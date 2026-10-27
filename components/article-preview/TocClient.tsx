"use client";

import { useEffect, useState } from "react";

type Heading = { id: string; text: string };

/** いま読んでいる章と、本文の読了率（0〜1） */
function useReading(headings: Heading[]) {
  const [active, setActive] = useState(-1);
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const flow = document.getElementById("article-flow");
      if (flow) {
        const rect = flow.getBoundingClientRect();
        const total = rect.height - window.innerHeight * 0.6;
        setProgress(Math.min(1, Math.max(0, -rect.top / Math.max(1, total))));
      }
      let current = -1;
      headings.forEach((h, i) => {
        const el = document.getElementById(h.id);
        if (el && el.getBoundingClientRect().top < 120) current = i;
      });
      setActive(current);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [headings]);
  return { active, progress };
}

/** B：PC の左に付いてくる目次。読了率と、いま読んでいる章を示す */
export function TocRail({ headings, minutes }: { headings: Heading[]; minutes: number }) {
  const { active, progress } = useReading(headings);
  const left = Math.max(0, Math.ceil(minutes * (1 - progress)));
  return (
    <nav aria-label="目次" className="sticky top-24">
      <div className="flex items-stretch text-meta font-bold">
        <span className="bg-accent px-2 py-1 tracking-[0.12em] text-accent-ink">目次</span>
        <span className="flex-1 bg-ink px-2 py-1 text-paper">
          <span className="index-num">{progress >= 0.99 ? "読了" : `残り約${left}分`}</span>
        </span>
      </div>
      <div className="h-[3px] bg-line" aria-hidden>
        <div className="h-full bg-live transition-[width] duration-150" style={{ width: `${progress * 100}%` }} />
      </div>
      <ol className="mt-2 grid">
        {headings.map((h, i) => (
          <li key={h.id}>
            <a
              href={`#${h.id}`}
              aria-current={i === active ? "location" : undefined}
              className={`grid grid-cols-[1.6rem_1fr] border-l-2 py-1.5 pl-2 pr-1 text-meta leading-snug transition-colors ${
                i === active ? "border-ink font-bold text-ink" : i < active ? "border-line-strong text-muted" : "border-line text-ink-soft hover:text-ink"
              }`}
            >
              <span className="index-num text-meta text-muted">{String(i + 1).padStart(2, "0")}</span>
              {h.text}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** C：画面上端の読了バーと、右下の「目次」ボタン（押すと章の一覧が開く） */
export function TocFloat({ headings }: { headings: Heading[] }) {
  const { active, progress } = useReading(headings);
  const [open, setOpen] = useState(false);
  const shown = progress > 0.01 && progress < 0.995;
  return (
    <>
      <div className="fixed inset-x-0 top-16 z-40 h-[3px]" aria-hidden>
        <div className="h-full bg-accent transition-[width] duration-150" style={{ width: `${progress * 100}%` }} />
      </div>
      {headings.length > 1 && (
        <div className={`fixed right-4 bottom-24 z-40 transition-opacity lg:bottom-6 ${shown || open ? "opacity-100" : "pointer-events-none opacity-0"}`}>
          {open && (
            <nav aria-label="目次" className="ap-toc-sheet mb-2 max-h-[60vh] w-[min(86vw,340px)] overflow-y-auto rounded-2xl border border-line-strong bg-paper p-2 shadow-xl">
              <ol className="grid">
                {headings.map((h, i) => (
                  <li key={h.id}>
                    <a
                      href={`#${h.id}`}
                      onClick={() => setOpen(false)}
                      className={`grid grid-cols-[1.75rem_1fr] items-baseline rounded-lg px-2.5 py-2 text-note leading-snug ${
                        i === active ? "bg-accent-soft font-bold text-ink" : "text-ink-soft hover:bg-surface"
                      }`}
                    >
                      <span className="index-num text-meta text-muted">{i + 1}</span>
                      {h.text}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          )}
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="ml-auto flex items-center gap-2 rounded-full bg-ink px-4 py-2.5 text-meta font-bold text-paper shadow-lg"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
              <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" strokeLinecap="round" />
            </svg>
            {open ? "閉じる" : `目次 ${active >= 0 ? `${active + 1}/${headings.length}` : ""}`}
          </button>
        </div>
      )}
    </>
  );
}
