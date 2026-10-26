import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { parsePage } from "@/lib/paginate";
import GenreView, { genreMetadata } from "../../view";

type Props = { params: Promise<{ genre: string; n: string }> };

// 2ページ目以降はアクセス時に生成してキャッシュする
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { genre, n } = await params;
  const page = parsePage(n);
  return page ? genreMetadata(genre, page) : {};
}

export default async function GenrePagedPage({ params }: Props) {
  const { genre, n } = await params;
  const page = parsePage(n);
  if (!page) notFound();
  return <GenreView genre={genre} page={page} />;
}
