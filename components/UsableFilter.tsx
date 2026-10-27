"use client";

import { useEffect, useState, type ReactNode } from "react";

const STORAGE_KEY = "saisoku:only-usable";

/**
 * 新着一覧の「今すぐ使えるものだけ」スイッチ。
 * 一覧はサーバーで描画済みなので、ここでは表示/非表示を CSS の属性で切り替えるだけ。
 */
export default function UsableFilter({ children }: { children: ReactNode }) {
  const [only, setOnly] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "1") setOnly(true);
    } catch {}
  }, []);

  const toggle = () => {
    const next = !only;
    setOnly(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {}
  };

  return (
    <div data-only-usable={only ? "1" : "0"} className="usable-filter">
      <div className="mb-3 flex justify-end">
        <button
          type="button"
          role="switch"
          aria-checked={only}
          onClick={toggle}
          className="flex items-center gap-2.5 rounded-full py-1 text-meta font-bold text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          今すぐ使えるものだけ
          <span
            aria-hidden
            className={`relative inline-block h-[20px] w-[36px] rounded-full transition-colors ${only ? "bg-go" : "bg-line-strong"}`}
          >
            <span
              className={`absolute top-[2px] size-4 rounded-full bg-paper shadow-sm transition-[left] motion-reduce:transition-none ${only ? "left-[18px]" : "left-[2px]"}`}
            />
          </span>
        </button>
      </div>
      {children}
      <p className="usable-empty hidden py-10 text-center text-meta text-muted">
        この中に、今すぐ使える発表はありません。
      </p>
    </div>
  );
}
