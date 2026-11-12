import type { Metadata } from "next";
import Link from "next/link";
import AssetShell, { Crumbs, QHeading } from "@/components/assets/AssetShell";
import { currentAnswer, getAllMoneyDates } from "@/lib/money-dates";
import { siteConfig } from "@/site.config";
import { pageShareImage } from "@/lib/page-share";

const TITLE = "暮らしとお金の日程　年金・児童手当・ボーナス・ふるさと納税はいつ？";
const DESCRIPTION =
  "年金と児童手当の12月の支給、公務員の冬のボーナスの支給日、ふるさと納税の期限、年賀はがき、個人向け国債の募集、電気・ガス料金の支援など、暮らしとお金の「いつ・いくら」を公式の発表で確かめて1ページずつまとめています。";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/dates" },
  openGraph: { siteName: siteConfig.siteName, locale: siteConfig.locale, type: "website", url: "/dates", title: "暮らしとお金の日程", description: DESCRIPTION,
    images: [{ url: pageShareImage("dates"), width: 1200, height: 630, alt: "暮らしとお金の日程" }] },
  twitter: { card: "summary_large_image", images: [pageShareImage("dates")] },
};

/** 暮らしとお金の日程の一覧 */
export default function MoneyDatesPage() {
  const all = getAllMoneyDates();
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "ItemList",
      name: "暮らしとお金の日程",
      itemListElement: all.map((entry, index) => ({
        "@type": "ListItem",
        position: index + 1,
        url: `${siteConfig.url}/dates/${entry.slug}`,
        name: entry.name,
      })),
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "ホーム", item: siteConfig.url },
        { "@type": "ListItem", position: 2, name: "暮らしとお金の日程", item: `${siteConfig.url}/dates` },
      ],
    },
  ];

  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { label: "暮らしとお金の日程" }]} />
      <header className="mt-5">
        <h1 className="t-h1">暮らしとお金の日程</h1>
        <p className="mt-3 text-desc leading-[1.85] text-ink-soft">
          支給日・期限・料金を、公式の発表で確かめて1ページずつまとめています。日付の横に出典と確認日を載せています。
        </p>
      </header>

      <section aria-labelledby="list-heading" className="mt-10">
        <QHeading id="list-heading">いつ・いくら？</QHeading>
        <ul className="grid gap-3">
          {all.map((entry) => {
            const answer = currentAnswer(entry);
            const first = answer.items[0];
            return (
              <li key={entry.slug}>
                <Link href={`/dates/${entry.slug}`} className="group block rounded-xl border border-line px-4 py-3.5 hover:border-ink">
                  <span className="text-meta font-bold text-muted">{entry.category}</span>
                  <span className="mt-0.5 block text-[16px] font-bold leading-snug text-ink group-hover:underline">{entry.name}</span>
                  {first && (
                    <span className="mt-1 block text-note text-ink-soft">
                      {first.label}：<strong className="font-bold text-ink">{first.value}</strong>
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      <p className="mt-8 text-note leading-[1.8] text-muted">
        上限額の計算は
        <Link href="/tools/furusato-limit" className="mx-1 font-bold text-ink-soft underline underline-offset-2 hover:text-ink">ふるさと納税の上限額の計算</Link>
        、手続きのやり方は
        <Link href="/guides" className="mx-1 font-bold text-ink-soft underline underline-offset-2 hover:text-ink">お金の手続きガイド</Link>
        にまとめています。
      </p>
    </AssetShell>
  );
}
