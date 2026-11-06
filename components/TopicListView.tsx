import Link from "next/link";
import { siteConfig } from "@/site.config";
import type { TopicEntryView } from "@/lib/topic-lists";

const when = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tokyo" });
const dayOnly = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${Number(m)}/${Number(d)}`;
};

/** 一覧の構造化データ（ItemList。中身は記事への内部リンク） */
export function topicListJsonLd(name: string, url: string, entries: TopicEntryView[], updatedAt: string) {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name,
    url: `${siteConfig.url}${url}`,
    dateModified: updatedAt,
    numberOfItems: entries.length,
    itemListElement: entries.map((e, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `${siteConfig.url}/articles/${e.slug}`,
      name: e.title,
    })),
  };
}

/** 一覧の本体（新しい順）。日時・会社・何が変わる・いつから・記事と公式の発表へのリンク */
export default function TopicListView({ entries }: { entries: TopicEntryView[] }) {
  if (entries.length === 0) {
    return <p className="mt-8 text-note text-muted">この期間に載せる発表はまだありません。公式の発表を確かめた記事ができると、ここに自動で足されます。</p>;
  }
  return (
    <ol className="mt-8 grid gap-3" data-topic-list>
      {entries.map((e) => (
        <li key={e.slug} className="rounded-xl border border-line p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-muted">
            <time dateTime={e.at} className="tabular-nums text-ink-soft">{when.format(new Date(e.at))}</time>
            <span className="rounded-[4px] bg-ink px-1.5 py-[1px] text-badge font-bold text-paper">{e.change}</span>
            {e.company && <span className="font-semibold text-ink-soft">{e.company}</span>}
            {e.effective && <span className="font-semibold text-accent">{e.effective}</span>}
          </div>
          <Link href={`/articles/${e.slug}`} className="mt-1.5 block text-[17px] font-bold leading-snug text-ink hover:underline">
            {e.title}
          </Link>
          {e.what && <p className="mt-1.5 text-desc leading-relaxed text-ink-soft">{e.what}</p>}
          <p className="mt-2 text-meta text-muted">
            公式の発表{e.announced ? `（${dayOnly(e.announced)}）` : ""}:{" "}
            <a href={e.sourceUrl} target="_blank" rel="noopener" className="underline underline-offset-2 hover:text-ink">
              {e.sourceName || "発表元"}
            </a>
          </p>
        </li>
      ))}
    </ol>
  );
}
