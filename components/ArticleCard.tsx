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
      className={`group overflow-hidden rounded-2xl border border-ink-100 bg-white transition-shadow hover:shadow-lg ${
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
            className={`mt-3 font-bold leading-snug text-ink-950 group-hover:text-accent ${
              featured ? "text-xl md:text-2xl" : "text-base"
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
