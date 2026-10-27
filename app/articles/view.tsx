import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ArticleCard from "@/components/ArticleCard";
import Pagination from "@/components/Pagination";
import { getAllArticles } from "@/lib/articles";
import { pageHref, pageSuffix, paginate } from "@/lib/paginate";

export function articlesMetadata(page: number): Metadata {
  return {
    title: `記事一覧${pageSuffix(page)}`,
    description:
      "AIが解析した世界のAI公式発表動画の解説記事をすべて時系列で掲載しています。",
    alternates: { canonical: pageHref("/articles", page) },
  };
}

export default function ArticlesView({ page }: { page: number }) {
  const articles = getAllArticles();
  const paged = paginate(articles, page);
  if (page > paged.totalPages) notFound();

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-12 sm:px-8">
      <h1 className="t-h1">
        記事一覧{pageSuffix(page)}
      </h1>
      <p className="mt-2 text-note text-muted">全 {articles.length} 本</p>

      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {paged.items.map((article, index) => (
          <ArticleCard
            key={article.slug}
            article={article}
            priority={page === 1 && index < 3}
          />
        ))}
      </div>

      <Pagination base="/articles" page={page} totalPages={paged.totalPages} />
    </div>
  );
}
