import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import DayLabel from "@/components/DayLabel";
import Thumb from "@/components/Thumb";
import UsableFilter from "@/components/UsableFilter";
import VerdictBadge from "@/components/VerdictBadge";
import type { Article } from "@/lib/articles";
import { companyOf, thumbSource } from "@/lib/companies";
import { Highlight } from "@/lib/highlight";
import { usability, verdictOf } from "@/lib/verdict";

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
export default function Timeline({
  articles,
  filterable = false,
}: {
  articles: Article[];
  /** 「今すぐ使えるものだけ」スイッチを出す */
  filterable?: boolean;
}) {
  const days: { day: string; items: Article[] }[] = [];
  for (const article of articles) {
    const day = jstDay(article.generatedAt || article.publishedAt);
    const last = days.at(-1);
    if (last?.day === day) last.items.push(article);
    else days.push({ day, items: [article] });
  }

  const list = (
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

  // 判定のある記事が一覧に無ければ、スイッチを出しても意味がない
  const hasVerdict = articles.some((article) => verdictOf(article));
  return filterable && hasVerdict ? <UsableFilter>{list}</UsableFilter> : list;
}

function TimelineRow({ article }: { article: Article }) {
  const company = companyOf(article);
  const point = article.highlights[0];
  const isRoundup = article.type === "roundup";
  // 一覧の時刻は「サイソクに載った時刻」。元動画の公開日は記事ページに出す
  const postedAt = article.generatedAt || article.publishedAt;
  const time = clock.format(Date.parse(postedAt));
  const verdict = verdictOf(article);
  const kind = verdict ? usability(verdict) : undefined;

  return (
    <li className="tl-row border-b border-line" data-usable={kind}>
      <Link
        href={`/articles/${article.slug}`}
        className="group grid grid-cols-1 gap-x-5 py-4 sm:grid-cols-[4rem_minmax(0,1fr)_11.5rem]"
      >
        {/* 幅のある画面では時刻と判定を左の列に、スマホでは企業名の横に置いて見出しの幅を確保する */}
        <div className="hidden content-start gap-2.5 sm:grid">
          <time
            dateTime={postedAt}
            className="index-num pt-[3px] text-[12px] font-semibold text-muted"
          >
            {time}
          </time>
          {kind && <VerdictBadge kind={kind} block />}
        </div>

        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px]">
            {kind && (
              <span className="sm:hidden">
                <VerdictBadge kind={kind} />
              </span>
            )}
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

          {verdict && (
            <p className="mt-1 text-[12.5px] text-muted">
              {[verdict.price !== "不明" ? verdict.price : "", verdict.japan === "ok" ? "日本から利用可" : verdict.japan === "no" && kind !== "wait" ? "日本では未提供" : "", verdict.audience ? `${verdict.audience}向け` : ""]
                .filter(Boolean)
                .join(" ・ ")}
            </p>
          )}

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
            // 一覧の小さな枠には軽い画像（480px）を使う。最高画質（1280px）は記事ページだけ
            src={article.thumbnail.replace("maxresdefault", "hqdefault")}
            source={thumbSource(article)}
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
