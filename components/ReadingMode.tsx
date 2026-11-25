"use client";

import { useEffect, useRef, useState } from "react";

const STORAGE_KEY = "saisoku:read-mode";
type Mode = "easy" | "expert";
type Load = "idle" | "loading" | "done" | "error";

/**
 * 「要約版で読む／詳細版で読む」の切り替え。サイソクの売りの1つ。
 * 2026-11-25 AdSense の点検: 記事ページの HTML には詳細版だけを入れる（両方を入れると同じ文がくり返されていた）。
 * 要約版は、読者が選んだときに /api/easy/<slug> から読み込み、#article-flow の [data-easy-body] に入れてから
 * data-read-mode を切り替える（lib/easy-version.ts）。選んだ読み方は覚えておき、次の記事でも同じ読み方で開く。
 * 読み込めなかったときは詳細版のままにし、その旨を短く出す。
 */
export default function ReadingMode({
  slug,
  noir = false,
  easyMinutes,
  expertMinutes,
}: {
  slug: string;
  noir?: boolean;
  easyMinutes: number;
  expertMinutes: number;
}) {
  const [mode, setMode] = useState<Mode>("expert");
  const [load, setLoad] = useState<Load>("idle");
  const loaded = useRef(false);

  const fetchEasy = async (): Promise<boolean> => {
    if (loaded.current) return true;
    const slot = document.querySelector<HTMLElement>("#article-flow [data-easy-body]");
    if (!slot) return false;
    setLoad("loading");
    try {
      const res = await fetch(`/api/easy/${encodeURIComponent(slug)}${noir ? "?v=noir" : ""}`, { headers: { accept: "application/json" } });
      const data = (await res.json()) as { html?: string };
      if (!res.ok || !data.html) throw new Error(`easy ${res.status}`);
      slot.innerHTML = data.html;
      loaded.current = true;
      setLoad("done");
      return true;
    } catch {
      setLoad("error");
      return false;
    }
  };

  const show = async (next: Mode, remember: boolean) => {
    if (next === "easy" && !(await fetchEasy())) {
      setMode("expert");
      apply("expert");
      return;
    }
    setMode(next);
    apply(next);
    if (remember) {
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {}
    }
  };

  useEffect(() => {
    let saved: Mode = "expert";
    try {
      if (localStorage.getItem(STORAGE_KEY) === "easy") saved = "easy";
    } catch {}
    if (saved === "easy") void show("easy", false);
    // 最初の1回だけ（slug が変わるのは別の記事のページ）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const options: { key: Mode; label: string; sub: string }[] = [
    { key: "easy", label: "要約版で読む", sub: `約${easyMinutes}分・用語を控えめに` },
    { key: "expert", label: "詳細版で読む", sub: `約${expertMinutes}分・数字や仕様まで` },
  ];

  return (
    <div className="mt-6 rounded-2xl border border-line-strong p-1.5" role="radiogroup" aria-label="記事の読み方">
      <div className="grid grid-cols-2 gap-1.5">
        {options.map((option) => {
          const active = mode === option.key;
          return (
            <button
              key={option.key}
              type="button"
              role="radio"
              aria-checked={active}
              aria-busy={option.key === "easy" && load === "loading"}
              onClick={() => void show(option.key, true)}
              className={`rounded-xl px-3 py-2.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
                active ? "bg-ink text-paper" : "text-ink hover:bg-surface"
              }`}
            >
              <span className="block text-note font-bold">{option.label}</span>
              <span className={`block text-meta ${active ? "opacity-75" : "text-muted"}`}>
                {option.key === "easy" && load === "loading" ? "読み込み中…" : option.sub}
              </span>
            </button>
          );
        })}
      </div>
      {load === "error" && (
        <p className="px-2 pb-1 pt-2 text-meta text-muted" role="status">
          要約版を読み込めませんでした。詳細版のまま表示しています。
        </p>
      )}
    </div>
  );
}

function apply(mode: Mode) {
  document.getElementById("article-flow")?.setAttribute("data-read-mode", mode);
}
