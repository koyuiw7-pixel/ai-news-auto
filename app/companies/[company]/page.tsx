import type { Metadata } from "next";
import { companyCounts } from "@/lib/companies";
import CompanyView, { aiArticles, companyMetadata } from "./view";

type Props = { params: Promise<{ company: string }> };

// 企業は数が限られるので全て静的化。新しい企業は初回アクセス時に生成（ISR）
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return companyCounts(aiArticles()).map(({ company }) => ({ company: company.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { company } = await params;
  return companyMetadata(company, 1);
}

/** 企業別の速報タイムライン。「OpenAI 最新」のような検索の受け皿にもなる */
export default async function CompanyPage({ params }: Props) {
  const { company } = await params;
  return <CompanyView slug={company} page={1} />;
}
