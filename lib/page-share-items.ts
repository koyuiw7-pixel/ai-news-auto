import type { Metadata } from "next";
import { getAllHowtos, getHowto } from "@/lib/howto";
import { getAllEvents, getEvent, localDateRange } from "@/lib/events";
import { getProduct, listedProducts } from "@/lib/products";
import { getAllChooseGuides, getChooseGuide } from "@/lib/choose";
import { currentAnswer, getAllMoneyDates, getMoneyDate } from "@/lib/money-dates";
import { PAGE_SHARE, PAGE_SHARE_KEYS, type PageShare, type PageShareKey } from "@/lib/page-share";

/**
 * ガイド・行事・製品・選び方ガイドの1ページずつのシェア画像（og:image。1200×630。SEO A15・2026-11-10）。
 * 形は lib/page-share.ts の固定ページと同じ（app/og/[key]/route.tsx がビルド時に描く。Workers では描かない）。
 * キーは「guide-<slug>」「event-<slug>」「product-<slug>」「choose-<slug>」「date-<slug>」。
 */
const PREFIX = { guide: "guide-", event: "event-", product: "product-", choose: "choose-", date: "date-" } as const;
export type ItemKind = keyof typeof PREFIX;

/** 題名を「大きな見出し」と「下の1行」に分ける（？・全角の空白・、で。分けられなければ全部を見出しに） */
export function splitTitle(title: string, maxHeading = 24): { heading: string; rest: string } {
  const text = title.replace(/[ \t\n]+/g, " ").trim();
  if (text.length <= maxHeading) return { heading: text, rest: "" };
  // 「？」「：」「。」は見出しに残す（「：」だけは外す）、次に全角の空白、最後に「、」で分ける
  for (const marks of [/[？?。]/g, /[：:]/g, /　/g, /、/g]) {
    for (const m of text.matchAll(marks)) {
      const at = m.index ?? -1;
      if (at < 4) continue;
      if (at >= maxHeading) break;
      // かっこの中では分けない（「NotebookLM（Gemini Notebook）」など）
      const head = text.slice(0, at);
      if ((head.match(/[（(]/g) ?? []).length > (head.match(/[）)]/g) ?? []).length) continue;
      const keep = /[？?。]/.test(m[0]) ? at + 1 : at;
      return { heading: text.slice(0, keep).replace(/。$/, ""), rest: text.slice(at + 1).trim() };
    }
  }
  return { heading: text, rest: "" };
}

/** 1行に収まるよう、区切り（、・　）の手前で切る。切れなければそのまま（画像側で折り返す） */
function fitLine(text: string, max = 30): string {
  if (text.length <= max) return text;
  const cut = Math.max(text.lastIndexOf("、", max), text.lastIndexOf("　", max), text.lastIndexOf("・", max), text.lastIndexOf(" ", max));
  return (cut >= 8 ? text.slice(0, cut) : text).replace(/[、,・\s]+$/, "");
}

function guideShare(slug: string): PageShare | undefined {
  const guide = getHowto(slug);
  if (!guide) return undefined;
  const { heading, rest } = splitTitle(guide.title);
  return {
    heading,
    // 分けられない長い題名は見出しだけで2〜3行になるので、下の1行目は空ける（同じ名前を繰り返さない）
    lines: [rest ? fitLine(rest) : heading.length > 17 ? "" : guide.toolName, guide.kind === "procedure" ? "公式の案内をもとに、手順と期限を1ページで" : "公式の情報をもとに、料金と使い方を1ページで"],
    footer: "サイソクのガイド",
  };
}

function eventShare(slug: string): PageShare | undefined {
  const event = getEvent(slug);
  if (!event) return undefined;
  return {
    heading: event.nameJa || event.name,
    lines: [fitLine(`${event.dateLabel ? `${event.startDate.slice(0, 4)}年${event.dateLabel}` : localDateRange(event)}${event.location ? `・${event.location.split(/[,、]/)[0].trim()}` : ""}`, 34), "日本時間の日程と、発表の要点"],
    footer: "サイソクの行事ガイド",
  };
}

function productShare(slug: string): PageShare | undefined {
  const product = getProduct(slug);
  if (!product) return undefined;
  return { heading: product.name, lines: [`${product.companyName}の${product.category}`, "できること・料金・最新ニュース"], footer: "サイソクのAIサービス図鑑" };
}

function chooseShare(slug: string): PageShare | undefined {
  const guide = getChooseGuide(slug);
  if (!guide) return undefined;
  const { heading, rest } = splitTitle(guide.h1);
  return { heading, lines: [fitLine(rest || "公式の情報で比べる"), "料金・条件・向いている人"], footer: "サイソクの選び方ガイド" };
}

/** 暮らしとお金の日程（/dates/<slug>）。画像には名前と一番の答え（日付・金額）を出す */
function dateShare(slug: string): PageShare | undefined {
  const entry = getMoneyDate(slug);
  if (!entry) return undefined;
  const first = currentAnswer(entry).items[0];
  return {
    heading: entry.name,
    lines: [first ? fitLine(`${first.label}：${first.value}`, 34) : "", "公式の発表で確かめた日付と金額"],
    footer: "サイソクの日程ガイド",
  };
}

/** キー → 画像の中身（固定ページ・1ページずつのどちらも） */
export function shareFor(key: string): PageShare | undefined {
  if (key in PAGE_SHARE) return PAGE_SHARE[key as PageShareKey];
  if (key.startsWith(PREFIX.guide)) return guideShare(key.slice(PREFIX.guide.length));
  if (key.startsWith(PREFIX.event)) return eventShare(key.slice(PREFIX.event.length));
  if (key.startsWith(PREFIX.product)) return productShare(key.slice(PREFIX.product.length));
  if (key.startsWith(PREFIX.choose)) return chooseShare(key.slice(PREFIX.choose.length));
  if (key.startsWith(PREFIX.date)) return dateShare(key.slice(PREFIX.date.length));
  return undefined;
}

/** ビルド時に描く画像のキー（固定ページ＋ガイド・行事・載せている製品・選び方ガイド） */
export function allShareKeys(): string[] {
  return [
    ...PAGE_SHARE_KEYS,
    ...getAllHowtos().map((g) => `${PREFIX.guide}${g.slug}`),
    ...getAllEvents().map((e) => `${PREFIX.event}${e.slug}`),
    ...listedProducts().map((p) => `${PREFIX.product}${p.slug}`),
    ...getAllChooseGuides().map((g) => `${PREFIX.choose}${g.slug}`),
    ...getAllMoneyDates().map((d) => `${PREFIX.date}${d.slug}`),
  ];
}

/** og:image の1枚（1200×630） */
export function itemShareImage(kind: ItemKind, slug: string, alt: string) {
  return { url: `/og/${PREFIX[kind]}${slug}`, width: 1200, height: 630, alt };
}

/** そのページの openGraph・twitter に画像を足す（Next は openGraph を浅く合わせるので、ページ側に images が要る） */
export function withItemImage<T extends Metadata>(meta: T, kind: ItemKind, slug: string, alt: string): T {
  const image = itemShareImage(kind, slug, alt);
  return {
    ...meta,
    openGraph: { ...(meta.openGraph ?? {}), images: [image] },
    twitter: { card: "summary_large_image", ...((meta.twitter as object) ?? {}), images: [image.url] },
  };
}
