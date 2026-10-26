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
    // 検索対象はAIジャンルが中心。幅広い話題の記事と同じく、一覧も検索結果には出さない
    robots: { index: false, follow: true },
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
      <h1 className="display mt-2 text-[1.9rem] sm:text-[2.3rem]">ニュース{pageSuffix(page)}</h1>
      <p className="mt-3 max-w-3xl text-[14.5px] leading-[1.9] text-muted">
        AIの速報に加えて、企業・研究機関・行政の公式発表から、暮らしや仕事に関わる話題を要点だけまとめています。
        {articles.length > 0 && <>全 {articles.length} 本。</>}
      </p>

      {articles.length === 0 ? (
        <p className="mt-16 text-center text-sm text-muted">まだ記事はありません。</p>
      ) : (
        <>
          <div className="mt-7 border-b border-ink pb-5">
            <GenreChips genres={genres} active="all" />
          </div>
          <div className="mt-8">
            <NewsGrid articles={paged.items} priority={page === 1 ? 4 : 0} />
          </div>
          <Pagination base="/news" page={page} totalPages={paged.totalPages} />
        </>
      )}
    </div>
  );
}
