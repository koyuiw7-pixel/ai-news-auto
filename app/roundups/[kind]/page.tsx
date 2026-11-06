import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AssetShell, { Crumbs } from "@/components/assets/AssetShell";
import TopicListView, { topicListJsonLd } from "@/components/TopicListView";
import {
  archiveMonths, MIN_INDEX_ENTRIES, monthLabel, RECENT_DAYS, recentEntries, TOPIC_LISTS, topicListsUpdatedAt, topicMeta, weekCount, type TopicKind,
} from "@/lib/topic-lists";

type Props = { params: Promise<{ kind: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return TOPIC_LISTS.map((m) => ({ kind: m.kind }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { kind } = await params;
  const meta = topicMeta(kind);
  if (!meta) return {};
  const entries = recentEntries(meta.kind);
  return {
    title: meta.title(weekCount(meta.kind)),
    description: meta.description,
    alternates: { canonical: `/roundups/${meta.kind}` },
    // 載っている発表が少ないうちは検索に出さない（薄いページにしない）
    ...(entries.length < MIN_INDEX_ENTRIES ? { robots: { index: false, follow: true } } : {}),
  };
}

/** 固定 URL の一覧（直近1か月・新しい順。記事ができるたびに更新） */
export default async function TopicListPage({ params }: Props) {
  const { kind } = await params;
  const meta = topicMeta(kind);
  if (!meta) notFound();
  const entries = recentEntries(meta.kind as TopicKind);
  const months = archiveMonths(meta.kind as TopicKind);
  const updatedAt = topicListsUpdatedAt();
  const updated = new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Tokyo" }).format(new Date(updatedAt));
  const week = weekCount(meta.kind as TopicKind);
  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(topicListJsonLd(meta.heading, `/roundups/${meta.kind}`, entries, updatedAt)) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { href: "/roundups", label: "一覧" }, { label: meta.label }]} />
      <h1 className="t-h1 mt-5">{meta.heading}</h1>
      <p className="t-lead mt-3">{meta.intro}</p>
      <p className="mt-2 text-meta text-muted">
        今週 {week} 件 / 直近{RECENT_DAYS}日 {entries.length} 件 ・ 最終更新: <time dateTime={updatedAt}>{updated}</time>
      </p>
      <TopicListView entries={entries} />
      {months.length > 0 && (
        <nav aria-label="月ごとの一覧" className="mt-10 border-t border-line pt-5">
          <h2 className="text-note font-bold text-ink">月ごとの一覧</h2>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-note">
            {months.map((m) => (
              <li key={m}><Link href={`/roundups/${meta.kind}/${m}`} className="underline underline-offset-2 hover:text-ink">{monthLabel(m)}</Link></li>
            ))}
          </ul>
        </nav>
      )}
      <p className="mt-8 text-meta text-muted">
        載せているのは、公式の発表を確かめて公開した記事だけです（事件・事故・芸能の話題は載せていません）。ほかの一覧:{" "}
        {TOPIC_LISTS.filter((m) => m.kind !== meta.kind).map((m, i) => (
          <span key={m.kind}>{i > 0 && "・"}<Link href={`/roundups/${m.kind}`} className="underline underline-offset-2 hover:text-ink">{m.label}</Link></span>
        ))}
      </p>
    </AssetShell>
  );
}
