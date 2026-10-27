"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** ヘッダーのメニュー。今いるページには赤い下線（選択中だけ赤） */
export default function HeaderNav({ items }: { items: { href: string; label: string }[] }) {
  const path = usePathname() ?? "/";
  return (
    <nav aria-label="メインメニュー" className="ml-auto hidden h-full items-center gap-5 md:flex lg:gap-7">
      {items.map((item) => {
        const current = item.href === "/" ? path === "/" : path === item.href || path.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className={`relative flex h-full items-center whitespace-nowrap text-note font-bold transition-colors after:absolute after:inset-x-0 after:bottom-0 after:h-[3px] after:bg-live after:transition-opacity hover:text-mast-ink ${
              current ? "text-mast-ink after:opacity-100" : "text-mast-muted after:opacity-0 hover:after:opacity-60"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
