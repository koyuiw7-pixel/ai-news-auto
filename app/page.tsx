import Link from "next/link";
import ArticleCard from "@/components/ArticleCard";
import {
  getAllArticles,
  getAllChannels,
  getAllGenres,
  getAllTags,
  getArticlesByGenre,
} from "@/lib/articles";
import { siteConfig } from "@/site.config";

export const revalidate = false;

export default function HomePage() {
  const articles = getAllArticles();
  const [featured, ...rest] = articles;
  const channels = getAllChannels();
  const genres = getAllGenres();
  const tags = getAllTags().slice(0, 24);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <section className="mb-14 border-b border-ink-100 pb-12">
        <p className="text-xs font-bold tracking-[0.2em] text-accent">
          AI NEWS — 世界のAI公式発表を日本語で
        </p>
        <h1 className="mt-4 font-serif text-[1.9rem] font-bold leading-[1.45] tracking-tight text-ink-950 sm:text-[2.6rem]">
          世界のAI公式発表を、
          <br className="sm:hidden" />
          <span className="relative whitespace-nowrap text-accent">
            映像ごとAI解析
          </span>
          して日本語速報。
        </h1>
        <p className="mt-5 max-w-3xl text-[15px] leading-[1.9] text-ink-500">
          {siteConfig.description}
        </p>
      </section>

      {articles.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <section>
            <h2 className="mb-5 text-sm font-bold tracking-widest text-ink-500">
              最新記事
            </h2>
            <div className="grid gap-6 md:grid-cols-3">
              <ArticleCard article={featured} priority featured />
              {rest.slice(0, siteConfig.topArticles).map((article) => (
                <ArticleCard key={article.slug} article={article} />
              ))}
            </div>
          </section>

          {articles.length > siteConfig.topArticles + 1 && (
            <div className="mt-10 text-center">
              <Link
                href="/articles"
                className="inline-block rounded-full bg-ink-950 px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-85"
              >
                すべての記事を見る（{articles.length}本）
              </Link>
            </div>
          )}

          {/* ジャンル別の最新記事 */}
          {genres.length > 1 &&
            genres.map((genre) => (
              <section key={genre.slug} className="mt-16">
                <div className="mb-5 flex items-baseline justify-between gap-4">
                  <h2 className="font-serif text-xl font-bold text-ink-950">
                    {genre.label}
                  </h2>
                  <Link
                    href={`/genres/${genre.slug}`}
                    className="shrink-0 text-sm font-medium text-accent hover:underline"
                  >
                    すべて見る（{genre.count}本）
                  </Link>
                </div>
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {getArticlesByGenre(genre.slug)
                    .slice(0, 3)
                    .map((item) => (
                      <ArticleCard key={item.slug} article={item} />
                    ))}
                </div>
              </section>
            ))}

          {channels.length > 0 && (
            <section className="mt-16">
              <h2 className="mb-5 text-sm font-bold tracking-widest text-ink-500">
                チャンネルから探す
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {channels.map((channel) => (
                  <Link
                    key={channel.slug}
                    href={`/channels/${channel.slug}`}
                    className="flex items-center justify-between rounded-xl border border-ink-100 bg-white px-5 py-4 transition-colors hover:border-accent hover:text-accent"
                  >
                    <span className="font-semibold">{channel.label}</span>
                    <span className="text-sm text-ink-300">
                      {channel.count}本
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {tags.length > 0 && (
            <section className="mt-16">
              <h2 className="mb-5 text-sm font-bold tracking-widest text-ink-500">
                トピックから探す
              </h2>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <Link
                    key={tag.slug}
                    href={`/tags/${tag.slug}`}
                    className="rounded-full border border-ink-100 bg-white px-4 py-2 text-sm text-ink-700 transition-colors hover:border-accent hover:text-accent"
                  >
                    #{tag.label}
                    <span className="ml-1.5 text-xs text-ink-300">
                      {tag.count}
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-ink-300 bg-white px-6 py-20 text-center">
      <p className="text-lg font-bold text-ink-950">記事はまだありません</p>
      <p className="mt-2 text-sm text-ink-500">
        GitHub Actions が 3 時間ごとに新着動画を解析して、自動で記事を追加します。
      </p>
      <p className="mt-4 inline-block rounded-lg bg-ink-50 px-4 py-2 font-mono text-xs text-ink-700">
        python3 scripts/main.py --max 1
      </p>
    </div>
  );
}
