import Link from "next/link";
import RelThumb from "@/components/noir/RelThumb";
import popular from "@/content/popular.json";
import { getAllArticles, getArticleSummary, type ArticleSummary } from "@/lib/articles";

/**
 * 右の列（PC）の記事の一覧。content/popular.json（scripts/popular_articles.py。自前の計測で今日と昨日に外から読まれた回数の多い順）が
 * あれば「よく読まれている記事」、無ければ（計測が取れない間）「新着記事」と名乗る（数えていない物を人気とは言わない）。
 */
const CORE = new Set(["public", "lifestyle", "investment", "business", "real-estate"]);

export default function NoirPopular({ current, limit = 5 }: { current: string; limit?: number }) {
  const ranked = ((popular as { items?: { slug: string }[] }).items ?? [])
    .map((item) => getArticleSummary(item.slug))
    .filter((a): a is ArticleSummary => Boolean(a) && a!.slug !== current)
    .slice(0, limit);
  const isRanked = ranked.length >= 3;
  const items = isRanked
    ? ranked
    : getAllArticles()
        .filter((a) => a.slug !== current && CORE.has(a.genreSlug))
        .slice(0, limit);
  if (items.length === 0) return null;
  return (
    <section className="nr-pop" aria-labelledby="nr-pop-heading">
      {/* 記事の外側の欄の見出しは h2 にしない（SEO A20） */}
      <p id="nr-pop-heading" className="nr-pop-h">{isRanked ? "よく読まれている記事" : "新着記事"}</p>
      <ol>
        {items.map((a, i) => (
          <li key={a.slug}>
            <Link href={`/articles/${a.slug}`}>
              {isRanked && <b aria-hidden>{i + 1}</b>}
              <span>{a.title}</span>
              <i className="nr-ph" aria-hidden>
                <RelThumb article={a} sizes="72px" />
              </i>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
