import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { parsePage } from "@/lib/paginate";
import NewsView, { newsMetadata } from "../../view";

type Props = { params: Promise<{ n: string }> };

// 2ページ目以降はアクセス時に生成してキャッシュする
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const page = parsePage((await params).n);
  return page ? newsMetadata(page) : {};
}

export default async function NewsPagedPage({ params }: Props) {
  const page = parsePage((await params).n);
  if (!page) notFound();
  return <NewsView page={page} />;
}
