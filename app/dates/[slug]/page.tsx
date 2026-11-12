import { articleTitle } from "@/lib/headline";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AssetShell, { Crumbs, QHeading } from "@/components/assets/AssetShell";
import ShareLinks from "@/components/assets/ShareLinks";
import {
  currentAnswer,
  currentTitle,
  daysUntilKey,
  getAllMoneyDates,
  getMoneyDate,
  moneyDateArticles,
  verifiedLabel,
  type DateSource,
} from "@/lib/money-dates";
import { authorJsonLd, publisherJsonLd } from "@/lib/publisher";
import { siteConfig } from "@/site.config";
import { withItemImage } from "@/lib/page-share-items";
import { Phrases } from "@/lib/highlight";
import { faqPageJsonLd } from "@/lib/structured-data";

type Props = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllMoneyDates().map((entry) => ({ slug: entry.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const entry = getMoneyDate(slug);
  if (!entry) return {};
  const title = currentTitle(entry);
  return withItemImage({
    title,
    description: entry.description,
    alternates: { canonical: `/dates/${entry.slug}` },
    openGraph: { siteName: siteConfig.siteName, locale: siteConfig.locale, type: "article", url: `/dates/${entry.slug}`, title, description: entry.description },
  }, "date", entry.slug, title);
}

const day = new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", weekday: "short", timeZone: "Asia/Tokyo" });

/** 暮らしとお金の日程ページ（答え → 決まり → よくある問い → 関連記事 → 出典） */
export default async function MoneyDatePage({ params }: Props) {
  const { slug } = await params;
  const entry = getMoneyDate(slug);
  if (!entry) notFound();

  const title = currentTitle(entry);
  const answer = currentAnswer(entry);
  const days = daysUntilKey(entry);
  const articles = moneyDateArticles(entry);
  const others = getAllMoneyDates().filter((d) => d.slug !== entry.slug);
  const url = `${siteConfig.url}/dates/${entry.slug}`;
  const checked = verifiedLabel(entry);

  // FAQPage は、ページに見出しとして出している問いと、その下に見えている答えだけで作る（SEO A18）
  const faq = entry.answers.map((item) => ({ q: item.q, a: item.a }));
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: title,
      description: entry.description,
      inLanguage: "ja",
      datePublished: `${entry.verifiedAt}T09:00:00+09:00`,
      dateModified: `${entry.verifiedAt}T09:00:00+09:00`,
      mainEntityOfPage: url,
      author: authorJsonLd,
      publisher: publisherJsonLd,
      citation: entry.sources.map((s) => ({ "@type": "CreativeWork", name: s.title, url: s.url })),
    },
    ...[faqPageJsonLd(faq)].filter((row) => row !== null),
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "ホーム", item: siteConfig.url },
        { "@type": "ListItem", position: 2, name: "暮らしとお金の日程", item: `${siteConfig.url}/dates` },
        { "@type": "ListItem", position: 3, name: entry.name, item: url },
      ],
    },
  ];

  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { href: "/dates", label: "暮らしとお金の日程" }, { label: entry.name }]} />

      <header className="mt-4">
        <p className="text-meta font-bold text-ink-soft">
          {entry.category}
          {days !== null && (
            <span className="ml-3 text-muted">
              {Number(entry.keyDate?.slice(5, 7))}月{Number(entry.keyDate?.slice(8, 10))}日
              {days === 0 ? "は今日です" : <>まで あと<span className="mx-0.5 tabular-nums">{days}</span>日</>}
            </span>
          )}
        </p>
        <h1 className="t-h1 mt-1.5"><Phrases text={title} /></h1>
      </header>

      {/* 答え（スマホの最初の画面に、出典と確認日といっしょに出す） */}
      <section aria-label={answer.label} className="mt-4 rounded-xl border-2 border-ink px-4 py-3.5 sm:px-5 sm:py-4">
        <p className="text-meta font-bold text-muted">{answer.label}</p>
        <dl className="mt-1.5 grid gap-y-1.5">
          {answer.items.map((item) => (
            <div key={item.label} className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)] items-baseline gap-x-3">
              <dt className="text-meta font-bold text-ink-soft">{item.label}</dt>
              <dd className="text-[17px] font-bold leading-snug tabular-nums text-ink">{item.value}</dd>
            </div>
          ))}
        </dl>
        {answer.note && <p className="mt-2 text-note leading-[1.7] text-ink-soft">{answer.note}</p>}
        <p className="mt-2 text-meta leading-[1.7] text-muted">
          出典：
          <a href={answer.source.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-ink">
            {answer.source.title}
          </a>
          <span className="ml-1">（確認日 {checked}）</span>
        </p>
      </section>

      <p className="mt-5 text-desc leading-[1.85] text-ink-soft">{entry.lead}</p>

      <section aria-labelledby="facts-heading" className="mt-10">
        <QHeading id="facts-heading">何が決まっている？</QHeading>
        <dl className="grid gap-x-6 rounded-xl border border-line p-4 text-note sm:grid-cols-[11rem_minmax(0,1fr)] sm:p-5">
          {entry.facts.map((fact) => (
            <div key={fact.label} className="contents">
              <dt className="pt-2.5 text-meta font-bold text-muted sm:py-2">{fact.label}</dt>
              <dd className="pb-2.5 text-ink sm:py-2">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {entry.answers.map((item, i) => (
        <section key={item.q} aria-labelledby={`answer-${i}`} className="mt-10">
          <QHeading id={`answer-${i}`}>{item.q}</QHeading>
          <p className="text-desc leading-[1.8] text-ink-soft">{item.a}</p>
          {item.sources && item.sources.length > 0 && <SourceLine sources={item.sources} checked={checked} />}
        </section>
      ))}

      {(entry.notes ?? []).length > 0 && (
        <div className="mt-8 rounded-xl bg-surface px-4 py-3 text-note leading-[1.8] text-ink-soft">
          {(entry.notes ?? []).map((line) => <p key={line}>{line}</p>)}
        </div>
      )}

      {entry.links.length > 0 && (
        <section aria-labelledby="links-heading" className="mt-12">
          <QHeading id="links-heading">あわせて確かめる</QHeading>
          <ul className="grid gap-2">
            {entry.links.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="block rounded-lg border border-line px-4 py-3 text-[15px] font-bold text-ink hover:border-ink hover:underline">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {articles.length > 0 && (
        <section aria-labelledby="articles-heading" className="mt-12">
          <QHeading id="articles-heading">関連するニュース</QHeading>
          <ul className="divide-y divide-line border-y border-line">
            {articles.map((article) => (
              <li key={article.slug} className="py-3.5">
                <p className="text-meta tabular-nums text-muted">{day.format(Date.parse(article.generatedAt || article.publishedAt))}</p>
                <Link href={`/articles/${article.slug}`} className="mt-1 block text-[15.5px] font-bold leading-snug text-ink hover:underline">
                  {articleTitle(article)}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="source-heading" className="mt-12">
        <QHeading id="source-heading">情報源は？</QHeading>
        <ul className="grid gap-1.5 text-note">
          {entry.sources.map((source) => (
            <li key={source.url}>
              <a href={source.url} target="_blank" rel="noopener noreferrer" className="break-all text-ink-soft underline underline-offset-2 hover:text-ink">
                {source.title}
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-note leading-[1.8] text-muted">
          日付と金額は{checked}に公式のページで確認しました。変更されることがあるので、手続きの前には公式のページも確かめてください。
        </p>
      </section>

      {others.length > 0 && (
        <section aria-labelledby="others-heading" className="mt-12">
          <QHeading id="others-heading">ほかのお金の日程は？</QHeading>
          <ul className="grid gap-2">
            {others.map((d) => (
              <li key={d.slug}>
                <Link href={`/dates/${d.slug}`} className="group flex flex-wrap items-baseline gap-x-3 gap-y-0.5 rounded-lg border border-line px-4 py-3 hover:border-ink">
                  <span className="text-meta text-muted">{d.category}</span>
                  <span className="text-[15px] font-bold text-ink group-hover:underline">{d.name}</span>
                </Link>
              </li>
            ))}
          </ul>
          <Link href="/dates" className="mt-4 inline-block text-note font-bold text-ink-soft hover:text-ink hover:underline">
            暮らしとお金の日程の一覧へ →
          </Link>
        </section>
      )}

      <div className="mt-12 border-t border-line pt-6">
        <ShareLinks url={url} title={title} />
      </div>
    </AssetShell>
  );
}

function SourceLine({ sources, checked }: { sources: DateSource[]; checked: string }) {
  return (
    <p className="mt-2 text-note leading-[1.8] text-muted">
      出典：
      {sources.map((src, j) => (
        <span key={src.url}>
          {j > 0 && "、"}
          <a href={src.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">{src.title}</a>
        </span>
      ))}
      （{checked}に確認）
    </p>
  );
}
