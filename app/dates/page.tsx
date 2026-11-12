import type { Metadata } from "next";
import Link from "next/link";
import AssetShell, { Crumbs, QHeading } from "@/components/assets/AssetShell";
import { currentAnswer, getAllMoneyDates } from "@/lib/money-dates";
import { siteConfig } from "@/site.config";
import { pageShareImage } from "@/lib/page-share";

const TITLE = "暮らしとお金の日程　支給日・期限・値上げ・制度の変更はいつから？";
const DESCRIPTION =
  "年金と児童手当の支給、確定申告の期間、携帯料金や食品の値上げ、タイヤやモバイルバッテリーのリコール、OTC類似薬の追加の負担、iDeCoの限度額など、暮らしとお金の「いつから・いくら・対象は」を公式の発表で確かめて1ページずつまとめています。";

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
  // 種類ごとにまとめる（JSON に最初に出てきた順）
  const groups = [...all.reduce((map, entry) => map.set(entry.category, [...(map.get(entry.category) ?? []), entry]), new Map<string, typeof all>())];
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

      {groups.map(([category, entries], g) => (
        <section key={category} aria-labelledby={`list-${g}`} className="mt-10">
          <QHeading id={`list-${g}`}>{category}</QHeading>
          <ul className="grid gap-3">
            {entries.map((entry) => {
              const answer = currentAnswer(entry);
              const first = answer.items[0];
              return (
                <li key={entry.slug}>
                  <Link href={`/dates/${entry.slug}`} className="group block rounded-xl border border-line px-4 py-3.5 hover:border-ink">
                    <span className="block text-[16px] font-bold leading-snug text-ink group-hover:underline">{entry.name}</span>
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
      ))}

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
