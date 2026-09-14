import Image from "next/image";
import Link from "next/link";
import Morph from "@/components/Morph";
import { formatDate, type Article } from "@/lib/articles";
import { Highlight } from "@/lib/highlight";

type Props = {
  article: Article;
  priority?: boolean;
  /** 記事ページへの画面遷移で、サムネイルと見出しをつなぐ。ページ内で同じ記事に1回だけ使う */
  morph?: boolean;
};

export default function ArticleCard({ article, priority, morph = false }: Props) {
  const isRoundup = article.type === "roundup";

  return (
    <article className="group h-full">
      <Link
        href={`/articles/${article.slug}`}
        className="flex h-full flex-col overflow-hidden rounded-2xl bg-surface transition duration-300 ease-out hover:-translate-y-0.5 hover:bg-surface-2"
      >
        <Morph name={`cover-${article.slug}`} enabled={morph}>
          <div className="relative aspect-video overflow-hidden bg-surface-2">
            <Image
              src={article.thumbnail}
              alt=""
              fill
              priority={priority}
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
              className="object-cover transition-transform duration-500 ease-out group-hover:scale-[1.04]"
            />
            <span className="absolute left-3 top-3 flex gap-1.5">
              {isRoundup && (
                <span className="rounded-full bg-ink px-2.5 py-0.5 text-[10.5px] font-bold text-paper">
                  まとめ
                </span>
              )}
              {article.genreSlug !== "ai" && (
                <span className="rounded-full bg-paper/90 px-2.5 py-0.5 text-[10.5px] font-bold text-ink">
                  {article.genre}
                </span>
              )}
            </span>
          </div>
        </Morph>

        <div className="flex flex-1 flex-col gap-2 p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-muted">
            <i className={`dot ${isRoundup ? "dot-roundup" : "dot-official"}`} aria-hidden />
            <span className="font-bold">{article.channel}</span>
            <time dateTime={article.publishedAt} className="index-num">
              {formatDate(article.publishedAt)}
            </time>
          </div>

          <Morph name={`title-${article.slug}`} enabled={morph}>
            <h3 className="text-[15.5px] font-bold leading-[1.6] text-ink [text-wrap:pretty]">
              <Highlight text={article.title} />
            </h3>
          </Morph>

          <p className="line-clamp-2 text-[14px] leading-[1.75] text-ink-soft">
            {article.description}
          </p>
        </div>
      </Link>
    </article>
  );
}
