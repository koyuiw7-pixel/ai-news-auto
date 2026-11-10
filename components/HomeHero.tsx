import Thumb from "@/components/Thumb";
import Link from "next/link";
import Morph from "@/components/Morph";
import { ArticleMark } from "@/components/CompanyMark";
import RelTime from "@/components/RelTime";
import type { ArticleSummary, ImageCredit as ImageCreditType } from "@/lib/articles";
import { containPhoto } from "@/lib/photo-fit";
import { smallThumb } from "@/lib/thumb-url";
import { companyOf, thumbSource } from "@/lib/companies";
import { Highlight } from "@/lib/highlight";
import { officialCreditText } from "@/lib/image-credit";
import ImageCredit from "@/components/ImageCredit";
import { coverPath, isFastNews } from "@/lib/cover-path";
import { liveLabel } from "@/lib/live-line";

/**
 * トップの主役。
 * 人は文字より画像を強く記憶する（画像優位性効果）ので、左に大きな写真、右に見出しを置く。
 * 強調は「何本を統合したか」の黒いバッジと、見出しの蛍光ペンの2か所だけに絞る。
 */
export default function HomeHero({ lead, popular = false }: { lead: ArticleSummary; popular?: boolean }) {
  const isRoundup = lead.type === "roundup";
  // 時刻は載せた時刻（下の一覧・記事の「公開」と同じ）。24時間を過ぎた主役は「最新」ではなく、読まれていれば「よく読まれています」（2026-11-11 読者目線レビュー 11位）
  const postedAt = lead.generatedAt || lead.publishedAt;
  const heroLabel = isRoundup ? "まとめ" : liveLabel({ fast: isFastNews(lead), publishedAt: postedAt }, Date.now()) ?? (popular ? "よく読まれています" : null);
  const sources = lead.sourceCount;
  const href = `/articles/${lead.slug}`;
  // 写真は photoOf（lib/article-index.mjs）が選んだもの。トップの主役は写真のある記事だけ（lib/home-lead.ts）。
  // 写真の出典: 公式発表の写真は会社・団体の名前、AI の絵（表紙用の AI のイメージも）は「AI生成」の札
  const photo = lead.photo;
  const fromThumbnail = Boolean(photo) && photo?.src === lead.thumbnail;
  const credit = fromThumbnail && !photo?.ai ? officialCreditText(lead.imageCredit) : null;
  const aiCredit: ImageCreditType | null = photo?.ai ? { kind: "ai", ...(photo.launch ? { launch: true } : {}) } : null;
  const contain = containPhoto(photo);

  return (
    <section
      aria-label="注目の記事"
      // 2026-11-10 オーナー「ホームは玄関」: 写真は見出しの上端にそろえる（縦の真ん中にそろえると写真の上に大きな空白ができていた）
      className="grid items-start gap-3 sm:gap-6 lg:grid-cols-[1.12fr_1fr] lg:gap-12"
    >
      <div className="min-w-0">
      <Link
        href={href}
        tabIndex={-1}
        aria-hidden
        className="group relative block overflow-hidden rounded-2xl bg-surface-2 sm:rounded-3xl"
      >
        <Morph name={`cover-${lead.slug}`}>
          <div className="relative aspect-[2/1] sm:aspect-video">
            {/* 縦長・文字の多い画像は切り抜かず、同じ画像をぼかした背景の上に丸ごと収める */}
            {photo && contain && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={smallThumb(photo.src)} alt="" aria-hidden decoding="async" className="absolute inset-0 size-full scale-110 object-cover opacity-60 blur-2xl" />
            )}
            <Thumb
              src={photo?.src ?? lead.thumbnail}
              source={thumbSource(lead)}
              cover={coverPath(lead)}
              alt=""
              fill
              pos={photo?.pos}
              contain={contain}
              // トップの LCP。他の画像より先に最優先で読む
              preload
              fetchPriority="high"
              sizes="(max-width: 1024px) 100vw, 640px"
              className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.03]"
            />
          </div>
        </Morph>
        {isRoundup && sources > 0 && (
          <span className="absolute bottom-4 left-4 inline-flex items-baseline gap-1.5 rounded-sm bg-ink/90 px-4 py-2 text-paper">
            <span className="index-num text-xl font-semibold leading-none">{sources}</span>
            <span className="text-meta font-bold">本の発表を統合</span>
          </span>
        )}
        {/* スマホは写真を小さくし、AI の札は写真の上に短く重ねる（下の2行の注記は PC だけ。最初の画面に見出しを並べるため。2026-11-11 読者目線レビュー 2位） */}
        {!credit && aiCredit && (
          <span data-allow-small="" className="absolute left-2 top-2 rounded-sm bg-ink/85 px-1.5 py-[1px] text-badge font-bold text-paper sm:hidden">
            {aiCredit.launch ? "AIで描いたイメージ" : "AI生成のイメージ"}
          </span>
        )}
      </Link>
      {/* 公式発表の写真は発表した会社・団体の名前を小さく添える（lib/image-credit.ts。記事ページと同じ文） */}
      {credit && <p className="mt-1.5 px-1 text-meta leading-relaxed text-ink-soft sm:mt-2 sm:text-note">{credit}</p>}
      {/* AI 生成の画像は本物の製品・人物と受け取られないよう、記事ページと同じ「AI生成」の札を出す */}
      {!credit && aiCredit && (
        <div className="hidden sm:block">
          <ImageCredit credit={aiCredit} className="mt-2 px-1" />
        </div>
      )}
      </div>

      <div className="flex min-w-0 flex-col gap-2 sm:gap-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-meta">
          {/* 赤は本当の速報だけ（ヘッダー下の帯と同じ判定 lib/live-line.ts。台帳 W23・2026-11-04 オーナー承認）。ほかは紺 */}
          {heroLabel && (
            <span
              data-hero-label={heroLabel}
              className={`rounded-sm px-2.5 py-0.5 text-badge font-bold tracking-wider ${heroLabel === "速報" ? "bg-live text-live-ink" : "bg-accent text-accent-ink"}`}
            >
              {heroLabel}
            </span>
          )}
          <ArticleMark company={companyOf(lead)} genre={lead.genre} size={18} />
          <RelTime iso={postedAt} className="index-num font-semibold text-muted" />
        </div>

        <Link href={href} className="group">
          <Morph name={`title-${lead.slug}`}>
            <h2 className="display font-bold text-[1.32rem] leading-[1.45] text-ink decoration-2 underline-offset-[6px] group-hover:underline sm:text-[2.05rem]">
              <Highlight text={lead.title} />
            </h2>
          </Morph>
        </Link>

        <p className="hidden text-desc leading-[1.85] text-ink-soft sm:line-clamp-2">
          {lead.lede || lead.description}
        </p>

        {lead.highlights.length > 0 && (
          <div className="hidden border-t border-line pt-4 sm:block">
            <p className="text-meta font-bold text-muted">この記事のポイント</p>
            <ol className="mt-2.5 grid gap-2.5">
              {lead.highlights.slice(0, 3).map((point, index) => (
                <li key={index} className="grid grid-cols-[22px_1fr] gap-3 text-desc leading-[1.7] text-ink">
                  <span className="index-num mt-0.5 grid size-[22px] place-items-center rounded-full bg-ink text-meta font-semibold text-paper">
                    {index + 1}
                  </span>
                  {point}
                </li>
              ))}
            </ol>
          </div>
        )}

        <Link
          href={href}
          className="mt-1 hidden w-fit items-center gap-2 rounded-md bg-ink sm:inline-flex px-5 py-2.5 text-note font-bold text-paper transition-opacity hover:opacity-85"
        >
          {isRoundup ? "まとめを読む" : "記事を読む"}
          <span aria-hidden>→</span>
        </Link>
      </div>
    </section>
  );
}
