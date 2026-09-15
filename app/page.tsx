import Link from "next/link";
import ArticleCard from "@/components/ArticleCard";
import CtaBanner from "@/components/CtaBanner";
import HomeHero from "@/components/HomeHero";
import IndexList from "@/components/IndexList";
import RoundupShelf from "@/components/RoundupShelf";
import Ticker from "@/components/Ticker";
import { getAllArticles, getAllGenres, tagSlug } from "@/lib/articles";
import { siteConfig } from "@/site.config";

export const revalidate = false;

const DAY_MS = 24 * 60 * 60 * 1000;

export default function HomePage() {
  // AI・テクノロジーに一点集中しているので、トップはAIジャンルだけで組む
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai");
  if (ai.length === 0) return <EmptyState />;

  const roundups = ai.filter((a) => a.type === "roundup");
  const official = ai.filter((a) => a.type !== "roundup");

  const lead = roundups[0] ?? official[0];
  const rest = official.filter((a) => a.slug !== lead.slug);

  // 最初の画面で同格に並べるのは3本まで（選択肢が多いほど迷うため）
  const cards = rest.slice(0, 3);
  const listed = rest.slice(3, 11);

  // 新しさの手がかり。ビルド時点の実データだけを出す
  const buildTime = Date.now();
  const updatedAt = ai
    .map((a) => a.generatedAt)
    .filter(Boolean)
    .sort()
    .at(-1);
  const recentCount = ai.filter(
    (a) => a.generatedAt && buildTime - Date.parse(a.generatedAt) < DAY_MS,
  ).length;

  // トピックはAI記事に付いているタグだけから集計する
  const tagCounts = new Map<string, { label: string; count: number }>();
  for (const article of ai) {
    for (const tag of article.tags) {
      const slug = tagSlug(tag);
      const entry = tagCounts.get(slug);
      if (entry) entry.count += 1;
      else tagCounts.set(slug, { label: tag, count: 1 });
    }
  }
  const tags = [...tagCounts.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 18);

  const otherGenres = getAllGenres().filter((g) => g.slug !== "ai");

  return (
    <>
      <Ticker items={ai.slice(0, 10)} updatedAt={updatedAt} recentCount={recentCount} />

      <div className="mx-auto grid max-w-[1180px] gap-20 px-5 pb-8 pt-10 sm:px-8 sm:pt-14">
        <HomeHero lead={lead} />

        {cards.length > 0 && (
          <section>
            <SectionHead eyebrow="LATEST" title="最新ニュース" href="/articles" />
            <div className="grid gap-x-7 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
              {cards.map((article, index) => (
                <ArticleCard key={article.slug} article={article} priority={index === 0} morph />
              ))}
            </div>
          </section>
        )}

        <RoundupShelf roundups={roundups.filter((r) => r.slug !== lead.slug).slice(0, 6)} />

        {listed.length > 0 && (
          <section>
            <SectionHead eyebrow="MORE" title="さらに読む" href="/articles" />
            <IndexList articles={listed} />
          </section>
        )}

        <CtaBanner genreSlug="ai" slot="primary" />

        {tags.length > 0 && (
          <section>
            <SectionHead eyebrow="TOPICS" title="トピックから探す" />
            <div className="flex flex-wrap gap-2">
              {tags.map(([slug, tag]) => (
                <Link
                  key={slug}
                  href={`/tags/${encodeURIComponent(slug)}`}
                  className="rounded-full border border-line px-3.5 py-1.5 text-[13.5px] font-medium text-ink-soft transition-colors hover:border-ink hover:text-ink"
                >
                  {tag.label}
                  <span className="index-num ml-2 text-[11px] text-muted">{tag.count}</span>
                </Link>
              ))}
            </div>
          </section>
        )}

        <footer className="grid gap-3 border-t border-line pt-8">
          <p className="max-w-[70ch] text-[13.5px] leading-relaxed text-ink-soft">
            {siteConfig.description}
          </p>
          {otherGenres.length > 0 && (
            <p className="text-[12.5px] text-muted">
              過去に扱っていた分野：
              {otherGenres.map((genre, index) => (
                <span key={genre.slug}>
                  {index > 0 && "、"}
                  <Link href={`/genres/${genre.slug}`} className="underline underline-offset-4 hover:text-ink">
                    {genre.label}
                  </Link>
                </span>
              ))}
            </p>
          )}
        </footer>
      </div>
    </>
  );
}

function SectionHead({
  eyebrow,
  title,
  href,
}: {
  eyebrow: string;
  title: string;
  href?: string;
}) {
  return (
    <div className="mb-7 flex items-end justify-between gap-4 border-b border-line-strong pb-3">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="display mt-1 text-2xl sm:text-[1.75rem]">{title}</h2>
      </div>
      {href && (
        <Link
          href={href}
          className="shrink-0 pb-1 text-[13px] font-bold text-muted transition-colors hover:text-ink"
        >
          すべて見る →
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
        GitHub Actions が6時間ごとに新着動画を解析して、自動で記事を追加します。
      </p>
    </div>
  );
}
