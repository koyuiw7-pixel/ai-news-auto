import type { Metadata } from "next";
import ArticleCard from "@/components/ArticleCard";
import { getAllArticles } from "@/lib/articles";

export const metadata: Metadata = {
  title: "記事一覧",
  description:
    "AIが解析した世界のAI公式発表動画の解説記事をすべて時系列で掲載しています。",
  alternates: { canonical: "/articles" },
};

export default function ArticlesIndexPage() {
  const articles = getAllArticles();

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-black tracking-tight text-ink-950 sm:text-3xl">
        記事一覧
      </h1>
      <p className="mt-2 text-sm text-ink-500">全 {articles.length} 本</p>

      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {articles.map((article, index) => (
          <ArticleCard
            key={article.slug}
            article={article}
            priority={index < 3}
          />
        ))}
      </div>
    </div>
  );
}
