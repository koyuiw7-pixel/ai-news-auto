import Image from "next/image";
import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";

/** 「01 ─ 見出し」形式の通し番号リスト。雑誌の目次に近い見せ方。 */
export default function IndexList({
  articles,
  start = 1,
}: {
  articles: Article[];
  start?: number;
}) {
  return (
    <ol className="border-t border-line">
      {articles.map((article, index) => (
        <li key={article.slug} className="border-b border-line">
          <Link
            href={`/articles/${article.slug}`}
            className="group flex items-start gap-4 py-5 sm:gap-6 sm:py-6"
          >
            <span className="index-num mt-1 shrink-0 text-sm font-bold text-accent">
              {String(start + index).padStart(2, "0")}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
                <span className="font-semibold tracking-widest text-accent">
                  {article.genre}
                </span>
                <span>{article.channel}</span>
                <time dateTime={article.publishedAt} className="index-num">
                  {formatDate(article.publishedAt)}
                </time>
              </div>

              <h3 className="mt-1.5 font-serif text-[1.0625rem] font-bold leading-[1.6] text-ink transition-colors group-hover:text-accent sm:text-[1.1875rem]">
                {article.title}
              </h3>

              <p className="mt-1.5 line-clamp-2 hidden text-sm leading-relaxed text-muted sm:block">
                {article.description}
              </p>
            </div>

            <div className="relative hidden aspect-[4/3] w-28 shrink-0 overflow-hidden rounded-lg bg-surface-2 sm:block">
              <Image
                src={article.thumbnail}
                alt=""
                fill
                sizes="112px"
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </div>
          </Link>
        </li>
      ))}
    </ol>
  );
}
