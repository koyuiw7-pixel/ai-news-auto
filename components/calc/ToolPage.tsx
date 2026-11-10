import type { ReactNode } from "react";
import Link from "next/link";
import AssetShell, { Crumbs } from "@/components/assets/AssetShell";
import { Calculator, CALC_NOTES } from "@/components/calc/CalculatorBox";
import { CALCULATORS, type CalculatorKind } from "@/lib/calculators";
import { siteConfig } from "@/site.config";
import { Phrases } from "@/lib/highlight";
import { moneyRowsForTool, toolRelatedArticleSlugs } from "@/lib/money-pages";
import { getAllArticles, getArticleSummary } from "@/lib/articles";
import { getHowto } from "@/lib/howto";
import { articleTitle } from "@/lib/headline";

/**
 * 計算機の単独ページ（/tools/*）の共通の枠。一覧（/tools）は無く、/tools は next.config.ts で転送する（2026-11-03）。
 * afterCalc は、計算の結果のすぐ下に置くもの（ふるさと納税の上限額のページの PR の囲みなど。2026-11-10）
 */
export default function ToolPage({ kind, lead, afterCalc, children }: { kind: CalculatorKind; lead: string; afterCalc?: ReactNode; children?: ReactNode }) {
  const meta = CALCULATORS[kind];
  const url = `${siteConfig.url}${meta.href}`;
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      name: meta.title,
      description: meta.description,
      url,
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      inLanguage: "ja",
      isAccessibleForFree: true,
      offers: { "@type": "Offer", price: 0, priceCurrency: "JPY" },
      publisher: { "@type": "Organization", name: siteConfig.siteName, url: siteConfig.url },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "ホーム", item: siteConfig.url },
        { "@type": "ListItem", position: 2, name: meta.title, item: url },
      ],
    },
  ];
  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { label: meta.title }]} />
      <header className="mt-5">
        <h1 className="t-h1 text-ink"><Phrases text={meta.title} /></h1>
        <p className="t-lead mt-3">{lead}</p>
      </header>
      <section aria-label="計算" className="mt-7 rounded-2xl border border-line-strong p-5 sm:p-6">
        <Calculator calc={{ kind }} />
      </section>
      <p className="mt-4 max-w-[40em] text-note leading-[1.75] text-ink-soft">{CALC_NOTES[kind]}</p>
      <p className="mt-2 max-w-[40em] text-note leading-[1.75] text-ink-soft">入力した数字は、この画面の中の計算だけに使います。送信・保存はしません。</p>
      {afterCalc}
      {children ? <div className="mt-12 max-w-[40em]">{children}</div> : null}
      <ToolRelated href={meta.href} />
    </AssetShell>
  );
}

/** 単独ページの説明の章 */
export function ToolSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10 first:mt-0">
      <h2 className="t-h2 border-b border-line-strong pb-2.5">{title}</h2>
      <div className="mt-4 grid gap-3 text-desc leading-[1.85] text-ink-soft">{children}</div>
    </section>
  );
}

/**
 * 計算ツールから、同じ話題の記事と手続きガイドへ（表は lib/money-pages.ts。2026-11-10 M2・SEO A12）。
 * 記事からツールへは calculatorForArticle（lib/calculators.ts）が案内するので、行き来できる。広告の枠と位置は変えない
 */
function ToolRelated({ href }: { href: string }) {
  const articles = toolRelatedArticleSlugs(href, getAllArticles()).flatMap((slug) => {
    const article = getArticleSummary(slug);
    return article ? [{ href: `/articles/${slug}`, label: articleTitle(article) }] : [];
  });
  const guides = [...new Set(moneyRowsForTool(href).flatMap((row) => row.guides ?? []))].flatMap((slug) => {
    const guide = getHowto(slug);
    return guide ? [{ href: `/guides/${slug}`, label: guide.title }] : [];
  });
  const links = [...articles, ...guides];
  if (links.length === 0) return null;
  return (
    <section aria-labelledby="tool-related-heading" className="mt-12 max-w-[40em]">
      <h2 id="tool-related-heading" className="t-h2 border-b border-line-strong pb-2.5">関連する記事とガイド</h2>
      <ul className="mt-4 grid list-disc gap-1.5 pl-5 text-desc leading-[1.85] text-ink-soft">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="text-accent underline underline-offset-4">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
