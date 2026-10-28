"use client";

import { useEffect, useRef, useState } from "react";
import type { OfferItem } from "@/lib/offers";
import { ProductImage, Rating, priceText, reasonOf } from "./parts";

const SEEN_KEY = "saisoku:offers-seen";
type Seen = Record<string, { n: number; at: number; clicked?: number }>;

function readSeen(): Seen {
  try {
    return JSON.parse(localStorage.getItem(SEEN_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function writeSeen(seen: Seen) {
  try {
    // 古いものから捨てて、記録は300件まで
    const entries = Object.entries(seen).sort((a, b) => b[1].at - a[1].at).slice(0, 300);
    localStorage.setItem(SEEN_KEY, JSON.stringify(Object.fromEntries(entries)));
  } catch {}
}

/**
 * 同じ人に同じ商品ばかり見せないための並べ替え。
 * 見た商品・押した商品はこの端末にだけ記録し、次からはまだ見ていない商品を先に出す。
 * 提携商品（単価が高い）は3回見るまでは下げない。押した商品は一番後ろへ。
 */
function demote(item: OfferItem, seen: Seen): number {
  const s = seen[item.key];
  if (!s) return 0;
  if (s.clicked) return 3;
  if (item.kind === "partner") return s.n >= 3 ? 2 : 0;
  return 1;
}

export default function RankingBody({
  items,
  visible = 3,
  wide,
  badge,
}: {
  items: OfferItem[];
  visible?: number;
  wide: boolean;
  badge: string;
}) {
  // 最初の表示はサーバーと同じ並び。読み込み後に、この端末の記録で並べ替える
  const [order, setOrder] = useState(items);
  const [ready, setReady] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const shown = order.slice(0, visible);

  useEffect(() => {
    const seen = readSeen();
    const sorted = items
      .map((item, i) => ({ item, i, d: demote(item, seen) }))
      .sort((a, b) => a.d - b.d || (seen[a.item.key]?.at ?? 0) - (seen[b.item.key]?.at ?? 0) || a.i - b.i)
      .map((x) => x.item);
    setOrder(sorted);
    setReady(true);
  }, [items]);

  const shownKey = shown.map((i) => i.key).join("|");

  // 画面に入ったら「見た」と記録する
  useEffect(() => {
    const el = root.current;
    if (!el || !ready) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        const seen = readSeen();
        const now = Date.now();
        for (const item of shown) seen[item.key] = { ...seen[item.key], n: (seen[item.key]?.n ?? 0) + 1, at: now };
        writeSeen(seen);
        io.disconnect();
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, shownKey]);

  const onClick = (item: OfferItem) => {
    const seen = readSeen();
    seen[item.key] = { n: seen[item.key]?.n ?? 1, at: Date.now(), clicked: Date.now() };
    writeSeen(seen);
  };

  const [first, ...rest] = shown;
  if (!first) return null;
  return (
    <div ref={root}>
      <First item={first} wide={wide} badge={badge} onClick={onClick} />
      {rest.length > 0 && (
        <ol className={wide ? "grid border-t border-line sm:grid-cols-2 sm:[&>li:nth-child(2)]:border-l sm:[&>li]:border-b-0" : ""} start={2}>
          {rest.map((item, index) => (
            <Row key={item.key} item={item} rank={index + 2} onClick={onClick} />
          ))}
        </ol>
      )}
    </div>
  );
}

function First({ item, wide, badge, onClick }: { item: OfferItem; wide: boolean; badge: string; onClick: (item: OfferItem) => void }) {
  const reason = reasonOf(item);
  return (
    <a
      href={item.url}
      target="_blank"
      rel="sponsored nofollow noopener noreferrer"
      data-aff-rank={1}
      onClick={() => onClick(item)}
      className={`group block ${wide ? "p-5 sm:p-6" : "border-b border-line p-4"}`}
    >
      <span className="flex items-center gap-2">
        <span className="font-display text-[34px] leading-none text-live">1</span>
        <span className="rounded-sm bg-live px-2.5 py-1 text-badge font-bold text-live-ink">{badge}</span>
        {item.label && <span className="text-meta font-bold text-live">{item.label}</span>}
      </span>

      <span className={wide ? "mt-3 grid gap-5 sm:grid-cols-[200px_minmax(0,1fr)]" : "block"}>
        <ProductImage
          item={item}
          className={`rounded-xl border border-line ${wide ? "aspect-square" : "mt-2.5 aspect-[16/10]"}`}
          pad={item.kind === "book" ? "p-5" : "p-3"}
          // 先読みすると本文の LCP と取り合う（スマホでは右枠はページの最下部）ので遅延読み込みのまま
        />
        <span className={`flex min-w-0 flex-col ${wide ? "" : "mt-2.5"}`}>
          <span className="line-clamp-2 text-[15px] font-bold leading-[1.5] text-ink group-hover:underline">{item.name}</span>
          {reason && (
            <span className="mt-1.5 rounded-lg bg-surface px-2.5 py-2 text-note leading-[1.6] text-ink-soft">
              <span className="font-bold text-ink">ここがおすすめ：</span>
              {reason}
            </span>
          )}
          <span className="mt-1.5">
            <Rating item={item} />
          </span>
          <span className="mt-1.5 flex items-baseline justify-between gap-2">
            <span className="index-num text-[23px] font-bold tracking-tight text-ink">{priceText(item)}</span>
            <span className="text-meta text-muted">{item.shop}</span>
          </span>
          <span className="mt-2.5 flex h-12 items-center justify-center gap-1.5 rounded-md bg-accent text-note font-bold text-accent-ink shadow-card transition-transform group-hover:-translate-y-px motion-reduce:transition-none">
            {item.cta}
            <span aria-hidden>↗</span>
          </span>
        </span>
      </span>
    </a>
  );
}

function Row({ item, rank, onClick }: { item: OfferItem; rank: number; onClick: (item: OfferItem) => void }) {
  return (
    <li className="border-b border-line last:border-b-0">
      <a
        href={item.url}
        target="_blank"
        rel="sponsored nofollow noopener noreferrer"
        data-aff-rank={rank}
        onClick={() => onClick(item)}
        className="group grid grid-cols-[22px_72px_minmax(0,1fr)] items-center gap-3 px-4 py-3.5 hover:bg-surface"
      >
        <span className="font-display text-[22px] leading-none text-ink">{rank}</span>
        <ProductImage item={item} className="size-[72px] rounded-lg border border-line" pad="p-1.5" />
        <span className="min-w-0">
          {item.label && <span className="block text-meta font-bold text-live">{item.label}</span>}
          <span className="line-clamp-2 text-meta font-bold leading-snug text-ink group-hover:underline">{item.name}</span>
          <span className="mt-0.5 block">
            <Rating item={item} size={11} />
          </span>
          <span className="mt-1 flex items-center justify-between gap-2">
            <span className="index-num text-note font-bold text-ink">{priceText(item)}</span>
            <span className="shrink-0 rounded-sm bg-ink px-2.5 py-1 text-badge font-bold text-paper group-hover:opacity-85">
              見る ↗
            </span>
          </span>
        </span>
      </a>
    </li>
  );
}
