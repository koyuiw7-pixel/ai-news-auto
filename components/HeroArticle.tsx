import Image from "next/image";
import Link from "next/link";
import { formatDate, type Article } from "@/lib/articles";

/** トップの主役。全幅画像に極大タイポを重ねるエディトリアル構成。 */
export default function HeroArticle({ article }: { article: Article }) {
  return (
    <Link
      href={`/articles/${article.slug}`}
      className="group relative block overflow-hidden rounded-2xl bg-black"
    >
      <div className="relative aspect-[16/10] sm:aspect-[21/9]">
        <Image
          src={article.thumbnail}
          alt={article.title}
          fill
          priority
          sizes="(max-width: 1240px) 100vw, 1240px"
          className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
        />
        <div className="scrim absolute inset-0" />
      </div>

      <div className="absolute inset-x-0 bottom-0 p-6 sm:p-10 lg:p-12">
        <div className="flex flex-wrap items-center gap-3 text-white/80">
          <span className="bg-accent px-2.5 py-1 text-[11px] font-bold tracking-[0.16em] text-accent-ink">
            {article.genre}
          </span>
          <span className="text-[11px] font-semibold tracking-widest">
            {article.channel}
          </span>
          <time
            dateTime={article.publishedAt}
            className="index-num text-[11px] text-white/60"
          >
            {formatDate(article.publishedAt)}
          </time>
        </div>

        <h2 className="display mt-4 max-w-4xl text-[1.6rem] text-white sm:text-[2.4rem] lg:text-[3rem]">
          {article.title}
        </h2>

        <p className="mt-4 hidden max-w-2xl text-sm leading-[1.9] text-white/70 sm:line-clamp-2 lg:block">
          {article.lede || article.description}
        </p>
      </div>
    </Link>
  );
}
