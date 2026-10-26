import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { parsePage } from "@/lib/paginate";
import TagView, { tagMetadata } from "../../view";

type Props = { params: Promise<{ tag: string; n: string }> };

// 2ページ目以降はアクセス時に生成してキャッシュする
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { tag, n } = await params;
  const page = parsePage(n);
  return page ? tagMetadata(tag, page) : {};
}

export default async function TagPagedPage({ params }: Props) {
  const { tag, n } = await params;
  const page = parsePage(n);
  if (!page) notFound();
  return <TagView tag={tag} page={page} />;
}
