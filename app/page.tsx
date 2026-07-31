import Link from "next/link";
import ArticleCard from "@/components/ArticleCard";
import HeroArticle from "@/components/HeroArticle";
import IndexList from "@/components/IndexList";
import {
  getAllArticles,
  getAllGenres,
  getAllTags,
  getArticlesByGenre,
} from "@/lib/articles";
import { siteConfig } from "@/site.config";

export const revalidate = false;

export default function HomePage() {
  const articles = getAllArticles();
  const [hero, ...rest] = articles;
  const genres = getAllGenres();
  const tags = getAllTags().slice(0, 20);

  if (articles.length === 0) return <EmptyState />;

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-8 sm:px-8 sm:py-12">
      {/* 主役記事 */}
      <HeroArticle article={hero} />

      {/* サブの主役3本 */}
      {rest.length > 0 && (
        <section className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {rest.slice(0, 3).map((article) => (
            <ArticleCard key={article.slug} article={article} priority />
          ))}
        </section>
      )}

      {/* 通し番号の目次リスト */}
      {rest.length > 3 && (
        <section className="mt-16">
          <SectionHead eyebrow="LATEST" title="新着記事" href="/articles" />
          <IndexList articles={rest.slice(3, 11)} start={5} />
        </section>
      )}

      {/* ジャンル別 */}
      {genres.map((genre) => {
        const items = getArticlesByGenre(genre.slug).slice(0, 3);
        if (items.length === 0) return null;
        return (
          <section key={genre.slug} className="mt-20">
            <SectionHead
              eyebrow={genre.slug === "ai" ? "TECHNOLOGY" : "REAL ESTATE"}
              title={genre.label}
              href={`/genres/${genre.slug}`}
              count={genre.count}
            />
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => (
                <ArticleCard key={item.slug} article={item} />
              ))}
            </div>
          </section>
        );
      })}

      {/* トピック */}
      {tags.length > 0 && (
        <section className="mt-20">
          <SectionHead eyebrow="TOPICS" title="トピックから探す" />
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <Link
                key={tag.slug}
                href={`/tags/${tag.slug}`}
                className="border border-line px-3.5 py-1.5 text-[13px] text-ink-soft transition-colors hover:border-accent hover:text-accent"
              >
                {tag.label}
                <span className="index-num ml-2 text-[11px] text-muted">
                  {tag.count}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <p className="mt-20 border-t border-line pt-8 text-[13px] leading-relaxed text-muted">
        {siteConfig.description}
      </p>
    </div>
  );
}

function SectionHead({
  eyebrow,
  title,
  href,
  count,
}: {
  eyebrow: string;
  title: string;
  href?: string;
  count?: number;
}) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4 border-b-2 border-ink pb-3">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="display mt-1 text-xl sm:text-2xl">{title}</h2>
      </div>
      {href && (
        <Link
          href={href}
          className="shrink-0 pb-1 text-[13px] font-semibold text-muted transition-colors hover:text-accent"
        >
          すべて見る{count ? `（${count}）` : ""} →
        </Link>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-32 text-center">
      <p className="eyebrow">NO ARTICLES YET</p>
      <p className="display mt-3 text-2xl">記事はまだありません</p>
      <p className="mt-4 text-sm leading-relaxed text-muted">
        GitHub Actions が3時間ごとに新着動画を解析して、自動で記事を追加します。
      </p>
      <p className="index-num mt-6 inline-block border border-line px-4 py-2 text-xs text-ink-soft">
        python3 scripts/main.py --max 1
      </p>
    </div>
  );
}
