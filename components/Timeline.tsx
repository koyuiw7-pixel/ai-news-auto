import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import DayLabel from "@/components/DayLabel";
import Thumb from "@/components/Thumb";
import type { Article } from "@/lib/articles";
import { companyOf } from "@/lib/companies";
import { Highlight } from "@/lib/highlight";

const clock = new Intl.DateTimeFormat("ja-JP", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Tokyo",
});
const jstDay = (iso: string) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(Date.parse(iso));

/**
 * 新着を時系列で並べる「速報の流れ」。
 * 1行に「いつ・どこが・何を・要点」を収め、記事を開かなくても流し読みで状況がつかめるようにする。
 * 要点は記事の「3秒でわかる要点」の1つ目。
 */
export default function Timeline({ articles }: { articles: Article[] }) {
  const days: { day: string; items: Article[] }[] = [];
  for (const article of articles) {
    const day = jstDay(article.publishedAt);
    const last = days.at(-1);
    if (last?.day === day) last.items.push(article);
    else days.push({ day, items: [article] });
  }

  return (
    <div className="grid gap-9">
      {days.map(({ day, items }) => (
        <section key={day} aria-label={day}>
          <h3 className="sticky top-16 z-10 -mx-1 flex items-baseline justify-between bg-paper/95 px-1 py-2 text-[13px] font-bold backdrop-blur">
            <DayLabel day={day} />
            <span className="index-num text-[11px] font-normal text-muted">{items.length}本</span>
          </h3>

          <ol className="border-t border-ink">
            {items.map((article) => (
              <TimelineRow key={article.slug} article={article} />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function TimelineRow({ article }: { article: Article }) {
  const company = companyOf(article);
  const point = article.highlights[0];
  const isRoundup = article.type === "roundup";
  const time = clock.format(Date.parse(article.publishedAt));

  return (
    <li className="border-b border-line">
      <Link
        href={`/articles/${article.slug}`}
        className="group grid grid-cols-1 gap-x-5 py-4 sm:grid-cols-[3.75rem_minmax(0,1fr)_11.5rem]"
      >
        {/* 幅のある画面では時刻を左の列に、スマホでは企業名の横に置いて見出しの幅を確保する */}
        <time
          dateTime={article.publishedAt}
          className="index-num hidden pt-[3px] text-[12px] font-semibold text-muted sm:block"
        >
          {time}
        </time>

        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px]">
            <span className="index-num font-semibold text-muted sm:hidden">{time}</span>
            <CompanyMark company={company} size={16} withName />
            {isRoundup && (
              <span className="rounded-full bg-ink px-2 py-[1px] text-[10.5px] font-bold text-paper">
                まとめ {article.sources?.length ?? 0}本
              </span>
            )}
          </p>

          <h4 className="mt-1.5 text-[15.5px] font-bold leading-[1.6] text-ink decoration-1 underline-offset-4 group-hover:underline sm:text-[16.5px]">
            <Highlight text={article.title} />
          </h4>

          {point && (
            <p className="mt-1.5 line-clamp-2 text-[13.5px] leading-[1.75] text-ink-soft">
              <span aria-hidden className="mr-1.5 font-bold text-accent">
                要点
              </span>
              {point}
            </p>
          )}
        </div>

        {/* スマホでは画像を省き、文字だけで速く流し読みできるようにする */}
        <div className="relative hidden aspect-video overflow-hidden rounded-lg bg-surface-2 sm:block">
          <Thumb
            src={article.thumbnail}
            alt=""
            fill
            sizes="184px"
            className="object-cover transition-transform duration-500 group-hover:scale-[1.04]"
          />
        </div>
      </Link>
    </li>
  );
}
