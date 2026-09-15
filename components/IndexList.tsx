import Thumb from "@/components/Thumb";
import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";
import { Highlight } from "@/lib/highlight";

/** 新着記事の一覧。時系列なので番号は振らず、日付と情報の種類で並べる */
export default function IndexList({
  articles,
}: {
  articles: Article[];
  start?: number;
}) {
  return (
    <ul className="divide-y divide-line border-y border-line">
      {articles.map((article) => (
        <li key={article.slug}>
          <Link
            href={`/articles/${article.slug}`}
            className="group grid grid-cols-[1fr_auto] items-start gap-4 py-4 sm:gap-6 sm:py-5"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-muted">
                <i
                  className={`dot ${article.type === "roundup" ? "dot-roundup" : "dot-official"}`}
                  aria-hidden
                />
                <time dateTime={article.publishedAt} className="index-num">
                  {formatDate(article.publishedAt)}
                </time>
                <span className="font-bold">{article.channel}</span>
              </div>

              <h3 className="mt-1.5 text-[15.5px] font-bold leading-[1.6] text-ink transition-colors group-hover:text-accent sm:text-[16.5px]">
                <Highlight text={article.title} />
              </h3>

              <p className="mt-1 hidden line-clamp-2 text-[14px] leading-[1.75] text-ink-soft sm:block">
                {article.description}
              </p>
            </div>

            <div className="relative hidden aspect-video w-32 shrink-0 overflow-hidden rounded-xl bg-surface-2 sm:block">
              <Thumb
                src={article.thumbnail}
                alt=""
                fill
                sizes="128px"
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
