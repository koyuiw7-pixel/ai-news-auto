import type { Metadata } from "next";
import { notFound } from "next/navigation";
import CompanyMark from "@/components/CompanyMark";
import LiveBar from "@/components/LiveBar";
import Timeline from "@/components/Timeline";
import { getAllArticles } from "@/lib/articles";
import { companyCounts, companyOf, getCompany } from "@/lib/companies";

type Props = { params: Promise<{ company: string }> };

export const dynamicParams = false;

const aiArticles = () => getAllArticles().filter((a) => a.genreSlug === "ai");

export function generateStaticParams() {
  return companyCounts(aiArticles()).map(({ company }) => ({ company: company.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { company: slug } = await params;
  const company = getCompany(slug);
  if (!company) return {};
  const count = aiArticles().filter((a) => companyOf(a).slug === slug).length;
  const name = company.slug === "other" ? "その他のAI企業" : company.name;

  return {
    title: `${name}の最新ニュース・発表まとめ`,
    description: `${name}の新モデル・新機能・料金などの最新発表を、日本語で要点だけ時系列にまとめています（${count}本）。`,
    alternates: { canonical: `/companies/${slug}` },
  };
}

/** 企業別の速報タイムライン。「OpenAI 最新」のような検索の受け皿にもなる */
export default async function CompanyPage({ params }: Props) {
  const { company: slug } = await params;
  const company = getCompany(slug);
  const all = aiArticles();
  const articles = all.filter((a) => companyOf(a).slug === slug);
  if (!company || articles.length === 0) notFound();

  const name = company.slug === "other" ? "その他のAI企業" : company.name;
  const updatedAt = articles.map((a) => a.generatedAt).filter(Boolean).sort().at(-1);
  const recentCount = articles.filter(
    (a) => a.generatedAt && Date.now() - Date.parse(a.generatedAt) < 86_400_000,
  ).length;

  return (
    <>
      <LiveBar
        updatedAt={updatedAt}
        recentCount={recentCount}
        weekCount={articles.filter((a) => a.generatedAt && Date.now() - Date.parse(a.generatedAt) < 7 * 86_400_000).length}
        companies={companyCounts(all).slice(0, 8)}
        active={slug}
      />
      <div className="mx-auto max-w-[920px] px-5 py-10 sm:px-8 sm:py-14">
        <div className="flex items-center gap-3">
          <CompanyMark company={company} size={40} />
          <p className="index-num text-[12px] font-semibold tracking-wider text-muted">
            {articles.length} 本の記事
          </p>
        </div>
        <h1 className="display mt-4 text-[1.9rem] sm:text-[2.4rem]">{name}の最新ニュース</h1>
        <p className="mt-3 max-w-[60ch] text-[14.5px] leading-[1.9] text-ink-soft">
          {name}の公式発表や解説動画を映像・音声ごと解析し、新しい順に並べています。
          各記事の「要点」だけ読めば、いま何が起きているかがつかめます。
        </p>
        <div className="mt-10">
          <Timeline articles={articles} filterable />
        </div>
      </div>
    </>
  );
}
