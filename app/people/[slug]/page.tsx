import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AssetShell, { Crumbs, QHeading } from "@/components/assets/AssetShell";
import Timeline from "@/components/Timeline";
import { getAllPeople, getPerson, personPage } from "@/lib/people";
import { siteConfig } from "@/site.config";
import { pageShareImage } from "@/lib/page-share";

type Props = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllPeople().map((p) => ({ slug: p.slug }));
}

function titleOf(nameJa: string, org: string, jobTitle: string, n: number): string {
  // A50: 読む人が得るもの（何者か・関連ニュースの本数）を先に。「〜とは？」にしない
  return `${nameJa}（${org} ${jobTitle.replace(/（.*?）/, "")}）の経歴と最新ニュース${n > 0 ? ` ${n}本` : ""}`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const person = getPerson(slug);
  if (!person) return {};
  const { own, indexable } = personPage(person);
  const n = own.length;
  const title = titleOf(person.nameJa, person.organization, person.jobTitle, n);
  const description =
    n > 0
      ? `${person.nameJa}（${person.name}）は${person.organization}の${person.jobTitle}。公式の発表で確かめた経歴と、サイソクの${person.nameJa}に関する記事${n}本を新しい順にまとめています。`
      : `${person.nameJa}（${person.name}）は${person.organization}の${person.jobTitle}。公式の発表で確かめた経歴と、${person.organization}の最新ニュースをまとめています。`;
  return {
    title,
    description,
    ...(indexable ? {} : { robots: { index: false, follow: true } }),
    alternates: { canonical: `/people/${person.slug}` },
    openGraph: { siteName: siteConfig.siteName, locale: siteConfig.locale, type: "profile", url: `/people/${person.slug}`, title, description,
      images: [{ url: pageShareImage("people"), width: 1200, height: 630, alt: title }] },
    twitter: { card: "summary_large_image", images: [pageShareImage("people")] },
  };
}

/** 人物のまとめページ（台帳 A53） */
export default async function PersonPage({ params }: Props) {
  const { slug } = await params;
  const person = getPerson(slug);
  if (!person) notFound();
  const { own: articles, org: orgArticles } = personPage(person);
  const url = `${siteConfig.url}/people/${person.slug}`;
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "ProfilePage",
      url,
      dateModified: person.verifiedAt,
      mainEntity: {
        "@type": "Person",
        name: person.name,
        alternateName: [person.nameJa, ...person.aliases],
        jobTitle: person.jobTitle,
        worksFor: { "@type": "Organization", name: person.organization, url: person.organizationUrl },
        sameAs: person.sameAs,
      },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "ホーム", item: siteConfig.url },
        { "@type": "ListItem", position: 2, name: "人物", item: `${siteConfig.url}/people` },
        { "@type": "ListItem", position: 3, name: person.nameJa, item: url },
      ],
    },
  ];
  return (
    <AssetShell>
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Crumbs items={[{ href: "/", label: "ホーム" }, { href: "/people", label: "人物" }, { label: person.nameJa }]} />
      <header className="mt-5">
        <h1 className="t-h1">{person.nameJa}（{person.name}）</h1>
        <p className="mt-3 text-desc leading-[1.85] text-ink-soft">{person.summary}</p>
      </header>

      <dl className="mt-6 grid gap-x-6 gap-y-2 rounded-xl border border-line p-4 text-note sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:p-5">
        <dt className="font-bold text-ink">所属</dt>
        <dd>
          <Link href={`/companies/${person.companySlug}`} className="underline underline-offset-2 hover:text-ink">{person.organization}</Link>
        </dd>
        <dt className="font-bold text-ink">役職</dt>
        <dd>{person.jobTitle}</dd>
        <dt className="font-bold text-ink">確認日</dt>
        <dd>{person.verifiedAt.replaceAll("-", "/")}（公式のページで確認）</dd>
      </dl>

      <section aria-labelledby="facts-heading" className="mt-10">
        <QHeading id="facts-heading" note="本人・所属組織の公式のページで確かめたことだけを書いています。">
          {person.nameJa}はどんな人？
        </QHeading>
        <ul className="grid gap-3">
          {person.facts.map((f) => (
            <li key={f.text} className="text-desc leading-[1.8] text-ink">
              {f.text}
              <span className="block text-meta text-muted">
                出典：<a href={f.source.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">{f.source.title}</a>
              </span>
            </li>
          ))}
        </ul>
      </section>

      {articles.length > 0 && (
        <section aria-labelledby="news-heading" className="mt-12">
          <QHeading id="news-heading">{person.nameJa}の最新ニュース（{articles.length}本）</QHeading>
          <Timeline articles={articles} />
        </section>
      )}

      {orgArticles.length > 0 && (
        <section aria-labelledby="org-heading" className="mt-12">
          <QHeading id="org-heading">
            {articles.length > 0 ? `${person.organization}の最新ニュース` : `${person.nameJa}が所属する${person.organization}の最新ニュース`}
          </QHeading>
          <Timeline articles={orgArticles} />
          <p className="mt-4 text-note">
            <Link href={`/companies/${person.companySlug}`} className="underline underline-offset-2 hover:text-ink">{person.organization}の記事をすべて見る</Link>
          </p>
        </section>
      )}
    </AssetShell>
  );
}
