"use client";

import { useEffect, useState } from "react";

type Mode = "light" | "dark" | "system";

/** layout.tsx の先読みスクリプトと同じキーを使う */
const STORAGE_KEY = "theme";

function apply(mode: Mode) {
  const root = document.documentElement;
  if (mode === "system") {
    root.removeAttribute("data-theme");
    localStorage.removeItem(STORAGE_KEY);
  } else {
    root.setAttribute("data-theme", mode);
    localStorage.setItem(STORAGE_KEY, mode);
  }
}

function resolve(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  // 既定は白。OSのダーク設定には追従しない
  return "light";
}

export default function ThemeToggle() {
  const [current, setCurrent] = useState<"light" | "dark">("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setCurrent(resolve());
    setMounted(true);
  }, []);

  function toggle() {
    const next = current === "dark" ? "light" : "dark";
    apply(next);
    setCurrent(next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={current === "dark" ? "ライトモードに切り替え" : "ダークモードに切り替え"}
      title={current === "dark" ? "ライトモードに切り替え" : "ダークモードに切り替え"}
      className="grid size-9 shrink-0 place-items-center rounded-full border border-line text-ink transition-colors hover:border-accent hover:text-accent"
    >
      {/* マウント前は SSR と一致させるため何も描かない（ハイドレーション差分の回避） */}
      {mounted &&
        (current === "dark" ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="12" cy="12" r="4.5" fill="currentColor" />
            <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.1 5.1l1.4 1.4M17.5 17.5l1.4 1.4M18.9 5.1l-1.4 1.4M6.5 17.5l-1.4 1.4" />
            </g>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
            <path
              fill="currentColor"
              d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.6 8.6 0 1 0 11.1 11.1Z"
            />
          </svg>
        ))}
    </button>
  );
}
