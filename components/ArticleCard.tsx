import Image from "next/image";
import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";

type Props = {
  article: Article;
  priority?: boolean;
};

export default function ArticleCard({ article, priority }: Props) {
  return (
    <article className="group">
      <Link href={`/articles/${article.slug}`} className="block">
        <div className="relative aspect-[16/10] overflow-hidden rounded-xl bg-surface-2">
          <Image
            src={article.thumbnail}
            alt={article.title}
            fill
            priority={priority}
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
            className="object-cover transition-transform duration-500 ease-out group-hover:scale-[1.05]"
          />
          <span className="absolute left-3 top-3 bg-accent px-2 py-0.5 text-[10px] font-bold tracking-[0.14em] text-accent-ink">
            {article.genre}
          </span>
        </div>

        <div className="pt-4">
          <div className="flex flex-wrap items-center gap-x-2.5 text-[11px] text-muted">
            <span className="font-semibold">{article.channel}</span>
            <span className="text-line-strong">/</span>
            <time dateTime={article.publishedAt} className="index-num">
              {formatDate(article.publishedAt)}
            </time>
          </div>

          <h2 className="mt-2 font-serif text-[1.0625rem] font-bold leading-[1.6] text-ink transition-colors group-hover:text-accent">
            {article.title}
          </h2>

          <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-muted">
            {article.description}
          </p>
        </div>
      </Link>
    </article>
  );
}
