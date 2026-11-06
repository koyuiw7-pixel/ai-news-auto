import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AssetShell, { Crumbs } from "@/components/assets/AssetShell";
import TopicListView, { topicListJsonLd } from "@/components/TopicListView";
import { archiveMonths, MIN_INDEX_ENTRIES, monthEntries, monthLabel, TOPIC_LISTS, topicListsUpdatedAt, topicMeta, type TopicKind } from "@/lib/topic-lists";

type Props = { params: Promise<{ kind: string; month: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return TOPIC_LISTS.flatMap((m) => archiveMonths(m.kind).map((month) => ({ kind: m.kind, month })));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { kind, month } = await params;
  const meta = topicMeta(kind);
  if (!meta || !/^\d{4}-\d{2}$/.test(month)) return {};
  const entries = monthEntries(meta.kind, month);
  return {
    title: `${monthLabel(month)}の${meta.label} ${entries.length}件の一覧`,
    description: `${monthLabel(month)}に公式の発表があった${meta.label}を、記事と公式の発表へのリンク付きで並べています。`,
    alternates: { canonical: `/roundups/${meta.kind}/${month}` },
    ...(entries.length < MIN_INDEX_ENTRIES ? { robots: { index: false, follow: true } } : {}),
  };
}

/** 月ごとの一覧（終わった月のアーカイブ） */
export default async function TopicListMonthPage({ params }: Props) {
  const { kind, month } = await params;
  const meta = topicMeta(kind);
  if (!meta || !archiveMonths(meta.kind as TopicKind).includes(month)) notFound();
  const entries = monthEntries(meta.kind as TopicKind, month);
  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(topicListJsonLd(`${monthLabel(month)}の${meta.label}`, `/roundups/${meta.kind}/${month}`, entries, topicListsUpdatedAt())) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { href: `/roundups/${meta.kind}`, label: meta.label }, { label: monthLabel(month) }]} />
      <h1 className="t-h1 mt-5">{monthLabel(month)}の{meta.label}</h1>
      <p className="mt-2 text-meta text-muted">{entries.length} 件 ・ <Link href={`/roundups/${meta.kind}`} className="underline underline-offset-2">最新の一覧へ</Link></p>
      <TopicListView entries={entries} />
    </AssetShell>
  );
}
