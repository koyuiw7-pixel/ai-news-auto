"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

type Item = { href: string; label: string };

/** 今いるページか。速報（/articles）は一覧とページ送りだけ（記事ページ /articles/◯◯ は含めない） */
function isCurrent(href: string, path: string): boolean {
  if (href === "/articles") return path === "/articles" || path.startsWith("/articles/page/");
  return path === href || path.startsWith(`${href}/`);
}

/**
 * ヘッダーの下のジャンルのタブ（スマホは横にスクロール、PC は1列に並ぶ）。
 * 今いるジャンルは文字を濃くして赤い下線。高さ 44px（指で押しやすい大きさ）で固定し、表示後に動かない。
 * lead（暮らしとお金の入口）はスマホ・タブレットだけタブの先頭に出す（PC はヘッダーの帯の右に出している。2026-11-11 読者目線レビュー 14位）。
 */
export default function GenreTabs({ items, lead }: { items: Item[]; lead: Item[] }) {
  const path = usePathname() ?? "/";
  const box = useRef<HTMLDivElement>(null);

  // 今いるタブが画面の外なら、横のスクロールだけで真ん中に寄せる（縦には動かさない）
  useEffect(() => {
    const el = box.current;
    const active = el?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!el || !active || el.scrollWidth <= el.clientWidth) return;
    el.scrollLeft = active.offsetLeft - (el.clientWidth - active.offsetWidth) / 2;
  }, [path]);

  const link = (item: Item) => {
    const current = isCurrent(item.href, path);
    const idle = "font-bold text-ink-soft";
    return (
      <Link
        href={item.href}
        aria-current={current ? "page" : undefined}
        className={`relative flex h-full items-center whitespace-nowrap text-note transition-colors after:absolute after:inset-x-0 after:bottom-0 after:h-[3px] after:bg-live after:transition-opacity hover:text-ink ${
          current ? "font-bold text-ink after:opacity-100" : `${idle} after:opacity-0 hover:after:opacity-50`
        }`}
      >
        {item.label}
      </Link>
    );
  };

  return (
    <nav aria-label="ジャンル" className="genre-tabs">
      <div
        ref={box}
        className="mx-auto max-w-[1240px] overflow-x-auto [mask-image:linear-gradient(to_right,#000_88%,transparent)] [scrollbar-width:none] lg:[mask-image:none] [&::-webkit-scrollbar]:hidden"
      >
        <ul className="flex h-11 w-max items-stretch gap-5 px-4 sm:px-8 lg:gap-4 xl:gap-6">
          {lead.map((item) => (
            <li key={item.href} className="flex lg:hidden">
              {link(item)}
            </li>
          ))}
          {lead.length > 0 && <li aria-hidden="true" className="my-3 w-px bg-line-strong lg:hidden" />}
          {items.map((item) => (
            <li key={item.href} className="flex">
              {link(item)}
            </li>
          ))}
          {/* 右端のぼかしで最後のタブが隠れないよう、少し余白を足す */}
          <li aria-hidden="true" className="w-6 lg:hidden" />
        </ul>
      </div>
    </nav>
  );
}
