import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GenreChips, NewsGrid } from "@/components/NewsHub";
import Pagination from "@/components/Pagination";
import { pageHref, pageSuffix, paginate } from "@/lib/paginate";
import { broadGenresWithArticles, getBroadArticles } from "@/lib/sections";

/** 1ページあたりの件数（4列で割り切れる数） */
const PER_PAGE = 48;

export function newsMetadata(page: number): Metadata {
  return {
    title: `ニュース｜ビジネス・テクノロジー・暮らし・科学ほか${pageSuffix(page)}`,
    description:
      "AI以外の話題も、企業・研究機関・行政の公式発表から要点だけを日本語でまとめています。ビジネス・ガジェット・暮らし・エンタメ・スポーツ・科学・社会の最新ニュース。",
    alternates: { canonical: pageHref("/news", page) },
  };
}

export default function NewsView({ page }: { page: number }) {
  const articles = getBroadArticles();
  const paged = paginate(articles, page, PER_PAGE);
  if (page > paged.totalPages) notFound();
  const genres = broadGenresWithArticles(articles);

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-12 sm:px-8">
      <p className="eyebrow">NEWS</p>
      <h1 className="t-h1 mt-2">ニュース{pageSuffix(page)}</h1>
      <p className="t-lead mt-3">
        AIの速報に加えて、企業・研究機関・行政の公式発表から、暮らしや仕事に関わる話題を要点だけまとめています。
        {articles.length > 0 && <>全 {articles.length} 本。</>}
      </p>

      {articles.length === 0 ? (
        <p className="mt-16 text-center text-note text-muted">まだ記事はありません。</p>
      ) : (
        <>
          <div className="mt-7 border-b border-ink pb-5">
            <GenreChips genres={genres} active="all" />
          </div>
          <div className="mt-8">
            {/* LCP は上の説明文。写真（配信元のまま数百KBのものもある）は先読みせず遅延読み込みにする */}
            <NewsGrid articles={paged.items} />
          </div>
          <Pagination base="/news" page={page} totalPages={paged.totalPages} />
        </>
      )}
    </div>
  );
}
