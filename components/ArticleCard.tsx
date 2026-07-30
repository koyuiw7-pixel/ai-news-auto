import Image from "next/image";
import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";

type Props = {
  article: Article;
  priority?: boolean;
  featured?: boolean;
};

export default function ArticleCard({ article, priority, featured }: Props) {
  return (
    <article
      className={`group overflow-hidden rounded-2xl border border-ink-100 bg-white transition-all duration-200 hover:-translate-y-0.5 hover:border-ink-300/60 hover:shadow-[0_12px_32px_-12px_rgba(15,23,42,0.18)] ${
        featured ? "md:col-span-2 md:row-span-2" : ""
      }`}
    >
      <Link href={`/articles/${article.slug}`} className="block">
        <div className="relative aspect-video overflow-hidden bg-ink-100">
          <Image
            src={article.thumbnail}
            alt={article.title}
            fill
            priority={priority}
            sizes={
              featured
                ? "(max-width: 768px) 100vw, 66vw"
                : "(max-width: 768px) 100vw, 33vw"
            }
            className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        </div>

        <div className={featured ? "p-6" : "p-5"}>
          <div className="flex items-center gap-2 text-xs font-medium text-ink-500">
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-accent">
              {article.channel}
            </span>
            <time dateTime={article.publishedAt}>
              {formatDate(article.publishedAt)}
            </time>
          </div>

          <h2
            className={`mt-3 font-serif font-bold leading-[1.5] text-ink-950 transition-colors group-hover:text-accent ${
              featured ? "text-xl md:text-[1.6rem]" : "text-[1.0625rem]"
            }`}
          >
            {article.title}
          </h2>

          <p
            className={`mt-2 text-sm leading-relaxed text-ink-500 ${
              featured ? "line-clamp-4" : "line-clamp-3"
            }`}
          >
            {article.description}
          </p>
        </div>
      </Link>
    </article>
  );
}
