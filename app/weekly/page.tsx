import type { Metadata } from "next";
import Link from "next/link";
import AssetShell, { Crumbs } from "@/components/assets/AssetShell";
import { getAllWeeks, weekRangeLabel } from "@/lib/weekly";
import { siteConfig } from "@/site.config";

const TITLE = "今週のAIニュースまとめ：1週間の重要な10本を2行で【毎週月曜更新】";
const DESCRIPTION =
  "OpenAI・Google・Anthropicなどの1週間のAIニュースから重要な10本を選び、何が起きたか・なぜ大事かを2行ずつまとめています。毎週月曜の朝7時に更新。";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/weekly", types: { "application/rss+xml": "/feed.xml" } },
  openGraph: { type: "website", url: "/weekly", title: "今週のAIニュースまとめ", description: DESCRIPTION },
};

/** 週まとめの一覧 */
export default function WeeklyIndexPage() {
  const weeks = getAllWeeks();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "今週のAIニュースまとめ",
    itemListElement: weeks.slice(0, 30).map((week, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: `${siteConfig.url}/weekly/${week.id}`,
      name: week.title,
    })),
  };

  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { label: "今週のAIニュース" }]} />
      <h1 className="mt-5 text-[1.75rem] font-bold leading-[1.35] text-ink sm:text-[2.2rem]">今週のAIニュースまとめ</h1>
      <p className="mt-3 max-w-[60ch] text-[14.5px] leading-[1.85] text-ink-soft">
        1週間のAIニュースから、押さえておきたい10本を選んでいます。1本ごとに「何が起きたか」「なぜ大事か」を2行で書いています。毎週月曜の朝7時に更新します。
      </p>
      <p className="mt-2 text-[12.5px] text-muted">
        RSSで受け取る: <a href="/feed.xml" className="underline underline-offset-2 hover:text-ink">/feed.xml</a>
      </p>

      {weeks.length === 0 ? (
        <p className="mt-10 text-[14px] text-muted">最初のまとめは次の月曜に公開します。</p>
      ) : (
        <ul className="mt-9 grid gap-4">
          {weeks.map((week, index) => (
            <li key={week.id}>
              <Link href={`/weekly/${week.id}`} className="group block rounded-xl border border-line p-4 transition-colors hover:border-ink sm:p-5">
                <span className="flex flex-wrap items-center gap-x-3 text-[12.5px] text-muted">
                  <span className="font-bold tabular-nums text-ink-soft">{weekRangeLabel(week)}</span>
                  {index === 0 && <span className="rounded-[4px] bg-ink px-1.5 py-[1px] text-[10.5px] font-bold text-paper">最新</span>}
                </span>
                <span className="mt-1.5 block text-[17px] font-bold leading-snug text-ink group-hover:underline">{week.title}</span>
                <ol className="mt-3 grid gap-1 text-[13.5px] leading-relaxed text-ink-soft">
                  {week.items.slice(0, 3).map((item, i) => (
                    <li key={item.slug} className="flex gap-2">
                      <span className="tabular-nums text-muted">{i + 1}.</span>
                      <span className="min-w-0">{item.title}</span>
                    </li>
                  ))}
                </ol>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AssetShell>
  );
}
