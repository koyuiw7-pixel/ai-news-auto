import Link from "next/link";
import { smallThumb } from "@/lib/thumb-url";
import popular from "@/content/popular.json";
import { getAllArticles, getArticleSummary, type ArticleSummary } from "@/lib/articles";
import { displayHeadline } from "@/lib/headline";

/** 暮らしとお金の分野（lib/home-lead.ts の LIFE_MONEY_GENRES と同じ） */
const CORE = new Set(["public", "lifestyle", "investment", "business", "real-estate"]);

/** よく読まれている記事（content/popular.json。自前の計測で今日と昨日に外から読まれた回数の多い順）。暮らしとお金の記事を先に */
export function popularReads(current: string, limit = 5): { items: ArticleSummary[]; ranked: boolean } {
  const ranked = ((popular as { items?: { slug: string }[] }).items ?? [])
    .map((item) => getArticleSummary(item.slug))
    .filter((a): a is ArticleSummary => Boolean(a) && a!.slug !== current);
  const core = ranked.filter((a) => CORE.has(a.genreSlug));
  const list = (core.length >= 3 ? core : ranked).slice(0, limit);
  if (list.length >= 3) return { items: list, ranked: true };
  return { items: getAllArticles().filter((a) => a.slug !== current && CORE.has(a.genreSlug)).slice(0, limit), ranked: false };
}

/**
 * 本文の直後の「よく読まれている記事」（上位5本・番号つき。2026-11-11 読者目線レビュー 4位）。
 * 以前はページのほぼ一番下（スマホで画面16〜18枚目）にあり、ほとんど見られていなかった。
 * 見た目は日経電子版のスマホのように、番号・太字の見出し・小さな写真だけ（オーナー 2026-11-11: 日経のスマホは読みやすい）。
 * 計測は今までの「次に読む記事」と同じ印（components/ReadingBeacon.tsx が next-read-heading を見る）
 */
export default function PopularReads({ current, className = "" }: { current: string; className?: string }) {
  const { items, ranked } = popularReads(current);
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="next-read-heading" data-popular-reads className={`mt-12 max-w-[46em] border-t-[3px] border-ink ${className}`}>
      {/* 記事の外側の欄の見出しは h2 にしない（SEO A20）。計測されていないときは「新着記事」と名乗る（数えていない物を人気とは言わない） */}
      <p id="next-read-heading" className="pb-1 pt-3 text-[17px] font-bold text-ink">
        {ranked ? "よく読まれている記事" : "暮らしとお金の新着記事"}
      </p>
      <ol>
        {items.map((a, i) => (
          <li key={a.slug} className="border-b border-line">
            <Link href={`/articles/${a.slug}`} className="group grid grid-cols-[auto_minmax(0,1fr)_80px] items-start gap-3 py-3.5">
              <b aria-hidden className="index-num min-w-[1.1em] text-[20px] font-bold leading-[1.2] text-accent">
                {i + 1}
              </b>
              <span className="text-[15.5px] font-bold leading-[1.55] text-ink group-hover:underline">{displayHeadline(a.title)}</span>
              <SmallPhoto article={a} />
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

/**
 * 小さな写真（幅 80px）。軽い <img> だけで描く（遅れて読む）。AI のイメージには「AI生成」の札（components/Thumb.tsx の AiMark と同じ見た目）。
 * 写真の無い記事はジャンル名の札（components/noir/RelThumb.tsx と同じ考え方）
 */
function SmallPhoto({ article }: { article: ArticleSummary }) {
  const photo = article.photo;
  return (
    <i className="relative block h-[45px] w-[80px] overflow-hidden rounded-[4px] bg-surface-2 not-italic" aria-hidden>
      {photo ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={smallThumb(photo.src)}
            alt=""
            loading="lazy"
            decoding="async"
            width={80}
            height={45}
            className={`size-full ${photo.fit === "contain" ? "object-contain" : "object-cover"}`}
            style={photo.pos ? { objectPosition: photo.pos } : undefined}
          />
          {photo.ai && (
            <span data-ai-mark="" className="pointer-events-none absolute bottom-0.5 left-0.5 rounded-sm bg-black/70 px-1 text-badge font-bold leading-[1.5] text-white">
              AI生成
            </span>
          )}
        </>
      ) : (
        <span className="grid size-full place-items-center bg-ink-soft px-1 text-center text-[11px] font-bold leading-tight text-paper">{article.genre}</span>
      )}
    </i>
  );
}
