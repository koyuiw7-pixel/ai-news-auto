import Link from "next/link";
import ArticleCard from "@/components/ArticleCard";
import Morph from "@/components/Morph";
import { formatDate, type Article } from "@/lib/articles";
import { Highlight } from "@/lib/highlight";

type Props = {
  /** 主役（最新のまとめ記事。無ければ最新記事） */
  lead: Article;
  /** 右列の新着 */
  latest: Article[];
  /** 下段のカード */
  cards: Article[];
};

/**
 * トップのベントーグリッド。
 * 主役・要点・新着・カードを大きさの違う区画で1画面に並べる。
 * 広い画面は12列、中くらいは6列、スマホは1列に組み替わる。
 */
export default function HomeBento({ lead, latest, cards }: Props) {
  const isRoundup = lead.type === "roundup";

  return (
    <section
      aria-label="注目の記事"
      className="grid grid-cols-1 gap-3.5 md:grid-cols-6 lg:grid-cols-12"
    >
      {/* 主役 */}
      <Link
        href={`/articles/${lead.slug}`}
        className="group flex flex-col gap-4 rounded-3xl bg-surface p-6 transition duration-300 ease-out hover:bg-surface-2 sm:p-8 md:col-span-6 lg:col-span-7 lg:row-span-2"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] font-bold">
          <span className={`inline-flex items-center gap-1.5 ${isRoundup ? "text-roundup" : "text-official"}`}>
            <i className={`dot ${isRoundup ? "dot-roundup" : "dot-official"}`} aria-hidden />
            {isRoundup ? "まとめ記事" : "公式発表"}
          </span>
          <time dateTime={lead.publishedAt} className="index-num font-normal text-muted">
            {formatDate(lead.publishedAt)}
          </time>
        </div>

        {isRoundup && (
          <div className="flex flex-wrap items-end gap-x-4 gap-y-1">
            <span className="index-num text-[clamp(4rem,9vw,6.5rem)] font-semibold leading-[0.85] tracking-tighter text-roundup">
              {lead.sources?.length ?? 0}
            </span>
            <span className="pb-1 text-[13.5px] font-bold leading-snug text-muted">
              本の発表を
              <br />
              1本に統合
            </span>
          </div>
        )}

        <Morph name={`title-${lead.slug}`}>
          <h2 className="display font-bold text-[1.75rem] text-ink sm:text-[2.1rem] lg:text-[2.4rem]">
            <Highlight text={lead.title} />
          </h2>
        </Morph>

        <p className="line-clamp-3 max-w-[52ch] text-[14.5px] leading-[1.9] text-ink-soft">
          {lead.lede || lead.description}
        </p>

        <span className="mt-auto inline-flex items-center gap-1.5 text-[13px] font-bold text-ink transition-colors group-hover:text-accent">
          {isRoundup ? "まとめを読む" : "記事を読む"}
          <span aria-hidden>→</span>
        </span>
      </Link>

      {/* 3秒でわかる要点 */}
      {lead.highlights.length > 0 && (
        <section
          aria-labelledby="bento-points"
          className="flex flex-col gap-4 rounded-3xl bg-surface p-6 md:col-span-3 lg:col-span-5"
        >
          <h2 id="bento-points" className="flex items-baseline justify-between gap-3 text-[13px] font-bold">
            3秒でわかる要点
            <span className="index-num truncate text-[10.5px] font-normal text-muted">
              {lead.sources?.length ? `${lead.sources.length} sources` : lead.channel}
            </span>
          </h2>
          <ol className="grid gap-3">
            {lead.highlights.slice(0, 3).map((point, index) => (
              <li key={index} className="grid grid-cols-[22px_1fr] gap-3 text-[14px] font-medium leading-[1.65] text-ink">
                <span className="index-num mt-0.5 grid size-[22px] place-items-center rounded-full bg-ink text-[11px] font-semibold text-paper">
                  {index + 1}
                </span>
                {point}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* 新着 */}
      {latest.length > 0 && (
        <section
          aria-labelledby="bento-latest"
          className="rounded-3xl bg-surface px-6 py-5 md:col-span-3 lg:col-span-5"
        >
          <h2 id="bento-latest" className="text-[13px] font-bold">
            新着
          </h2>
          <ul className="mt-2 divide-y divide-line">
            {latest.map((article) => (
              <li key={article.slug}>
                <Link href={`/articles/${article.slug}`} className="group grid grid-cols-[8px_1fr] gap-3 py-3">
                  <i className="dot dot-official mt-2" aria-hidden />
                  <span className="min-w-0">
                    <span className="flex gap-2.5 text-[10.5px] text-muted">
                      <time dateTime={article.publishedAt} className="index-num">
                        {formatDate(article.publishedAt)}
                      </time>
                      <span className="truncate">{article.channel}</span>
                    </span>
                    <span className="mt-0.5 block text-[13.5px] font-bold leading-[1.55] text-ink transition-colors group-hover:text-accent">
                      {article.title}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* カード */}
      {cards.map((article, index) => (
        <div key={article.slug} className="md:col-span-3 lg:col-span-4">
          <ArticleCard article={article} priority={index === 0} morph />
        </div>
      ))}
    </section>
  );
}
