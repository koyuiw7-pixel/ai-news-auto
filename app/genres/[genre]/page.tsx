import type { Metadata } from "next";
import { getAllGenres } from "@/lib/articles";
import GenreView, { genreMetadata } from "./view";

type Props = { params: Promise<{ genre: string }> };

// ジャンルは数が少ないので全て静的化。新しいジャンルは初回アクセス時に生成（ISR）
export const dynamicParams = true;
export const revalidate = 86400;

export function generateStaticParams() {
  return getAllGenres().map((genre) => ({ genre: genre.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { genre } = await params;
  return genreMetadata(genre, 1);
}

export default async function GenrePage({ params }: Props) {
  const { genre } = await params;
  return <GenreView genre={genre} page={1} />;
}
