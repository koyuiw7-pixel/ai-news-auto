"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import RelTime from "@/components/RelTime";
import { PushBell } from "@/components/PushOptIn";

type Item = { slug: string; title: string; publishedAt: string };

/** ヘッダー下の速報の1行。トップでは先頭の大きな記事と重ならないよう2番目を出す。右端に通知の鈴 */
export default function LiveLine({ items }: { items: [Item, Item] | Item[] }) {
  const path = usePathname() ?? "/";
  const item = path === "/" ? (items[1] ?? items[0]) : items[0];
  if (!item) return null;
  return (
    <div className="live-line">
      <div className="mx-auto flex h-9 max-w-[1240px] items-center gap-2.5 px-4 text-meta sm:px-8">
        <span className="shrink-0 rounded-sm bg-live px-1.5 py-[1px] text-badge font-bold tracking-[0.06em] text-live-ink">速報</span>
        <RelTime iso={item.publishedAt} className="index-num shrink-0 text-muted" />
        <Link
          href={`/articles/${item.slug}`}
          className="min-w-0 truncate font-bold text-ink underline-offset-[3px] hover:underline"
        >
          {item.title}
        </Link>
        {/* 速報のプッシュ通知（押すと説明の吹き出し → 登録） */}
        <PushBell />
      </div>
    </div>
  );
}
