import type { Metadata } from "next";
import Link from "next/link";
import { getAllChooseGuides } from "@/lib/choose";
import { guideShortName, LIFE_COMPARE_SLUGS, lifeCompareGuide } from "@/lib/buying-guides";
import { siteConfig } from "@/site.config";
import { CALCULATORS } from "@/lib/calculators";
import { pageShareImage } from "@/lib/page-share";

/**
 * 選び方ガイドの一覧（/choose。2026-11-10 M6）。今までは /choose/* だけがあり、/choose は 404 だった。
 * 暮らしとお金の比較ページ（lib/buying-guides.ts の LIFE_COMPARE_SLUGS）と、AI の選び方ガイド（lib/choose-data.ts）を並べる。
 * 検索の扱い（robots）は /choose/* と同じ（指定しない）。広告は置かない（サイト内リンクだけ）。
 */
export const metadata: Metadata = {
  title: "選び方ガイドの一覧",
  description: "格安SIM、光回線、電気・ガス、保険相談の窓口、ふるさと納税サイトの比較と、通信回線・Difyの使い方・AI転職の選び方ガイドの一覧です。",
  alternates: { canonical: "/choose" },
  openGraph: {
    siteName: siteConfig.siteName,
    locale: siteConfig.locale,
    type: "website",
    url: "/choose",
    title: "選び方ガイドの一覧",
    description: "暮らしとお金の比較ページと、AIの選び方ガイドの一覧です。",
    images: [{ url: pageShareImage("choose"), width: 1200, height: 630, alt: "選び方ガイドの一覧" }],
  },
  twitter: { card: "summary_large_image", images: [pageShareImage("choose")] },
};

export default function ChooseIndexPage() {
  const compares = LIFE_COMPARE_SLUGS.flatMap((slug) => {
    const found = lifeCompareGuide(slug);
    return found ? [{ href: found.href, title: `${guideShortName(found.guide)}の比較`, note: found.guide.description }] : [];
  });
  // お金の計算ツール（ヘッダーの「比較・計算」の入口。2026-11-11 読者目線レビュー 14位）。10〜12月はふるさと納税を先に
  const tools = [CALCULATORS["furusato-limit"], CALCULATORS["defense-tax"]].map((t) => ({ href: t.href, title: t.title, note: t.description }));
  const chooses = getAllChooseGuides().map((guide) => ({ href: `/choose/${guide.slug}`, title: guide.articleLabel, note: guide.articleNote }));

  return (
    <div className="mx-auto max-w-[920px] px-5 py-10 sm:px-8 sm:py-14">
      <p className="eyebrow">CHOOSE</p>
      <h1 className="t-h1 mt-2">選び方ガイドの一覧</h1>
      <p className="t-lead mt-3">料金や条件を、各社の公式サイトの記載をもとに比べたページと、お金の計算ツールです。</p>

      <section aria-labelledby="choose-calc" className="mt-10">
        <h2 id="choose-calc" className="t-h2">お金の計算</h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {tools.map((item) => (
            <li key={item.href}>
              <ChooseCard {...item} money />
            </li>
          ))}
        </ul>
      </section>

      {compares.length > 0 && (
        <section aria-labelledby="choose-money" className="mt-12">
          <h2 id="choose-money" className="t-h2">暮らしとお金の比較</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {compares.map((item) => (
              <li key={item.href}>
                <ChooseCard {...item} money />
              </li>
            ))}
          </ul>
        </section>
      )}

      {chooses.length > 0 && (
        <section aria-labelledby="choose-ai" className="mt-12">
          <h2 id="choose-ai" className="t-h2">AIを使うための選び方</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {chooses.map((item) => (
              <li key={item.href}>
                <ChooseCard {...item} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ChooseCard({ href, title, note, money = false }: { href: string; title: string; note: string; money?: boolean }) {
  return (
    <Link
      href={href}
      {...(money ? { "data-money-link": "" } : {})}
      className="group block h-full rounded-2xl border border-line p-4 transition-colors hover:border-ink"
    >
      <span className="block text-[16.5px] font-bold leading-snug text-ink group-hover:underline">{title}</span>
      <span className="mt-1.5 line-clamp-3 block text-desc leading-[1.7] text-ink-soft">{note}</span>
    </Link>
  );
}
