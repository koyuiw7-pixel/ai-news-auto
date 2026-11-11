import type { ReactNode } from "react";
import Link from "next/link";
import Thumb from "@/components/Thumb";
import RelThumb from "@/components/noir/RelThumb";
import ArticleProse from "@/components/ArticleProse";
import ImageCredit from "@/components/ImageCredit";
import NoirChrome from "@/components/noir/NoirChrome";
import NoirFonts, { noirFontHref } from "@/components/noir/NoirFonts";
import { announcedAt, formatDate, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { NOIR_AI_TAG, displayGlyphs, noirKeyFigure, splitEmphasis, type NoirCover } from "@/lib/noir";
import { stripListNumber } from "@/lib/list-number";
import { bylineDates } from "@/lib/byline";
import { siteConfig } from "@/site.config";
import "./noir.css";

/**
 * 新しい記事の見た目「ノワール」（2026-11-07 オーナー承認・台帳 W36）。layout が "noir" の記事だけ。
 *
 * 2026-11-09 オーナー（PC で見て「広告が一番下だけ」「色がくすんでいる」「写真が無く文字だけ」「左右の余白が広すぎる」「続きが文字の壁」）を受けて組み直した:
 *  - サイトの帯（ロゴ・ジャンル）をそのまま出し、PC（1024px 以上）は本文 + 右の列（商品の枠・よく読まれている記事。追従）の2列。幅は最大 1160px
 *  - 題名の下に表紙の写真（16:9）と出典・AI の札。本物の写真が無い記事は写真の場所を作らない（文字だけの偽の表紙は出さない）
 *  - 要点 → すぐにできること（短い一覧）→ 1つ目の PR → なるほど → 本文。本文の途中に2つ目、記事の終わりに3つ目（本文の列は最大3つ）
 *  - 本文は章ごとに見出しの赤い線・数字の印・一覧のカード・色の付いた欄（なるほど＝黄・公式窓口＝青・判断ガイド＝緑・不安Q&A＝赤）で区切る
 * 見出し・構造化データ・広告・提携・計測・オーナーのルールの部品は、今までの記事ページ（app/articles/[slug]/page.tsx）で作った物をそのまま受け取って並べる。
 * 「このニュースを3行で」「何が起きた」「KEY NUMBERS」のような決まった型の見出しは付けない（オーナーが AI っぽいと判断）。
 */
export type NoirProps = {
  article: FullArticle;
  title: string;
  jsonLd: unknown;
  /** 表紙の写真（lib/noir.ts の noirCover）。null なら写真の場所を作らない */
  cover: NoirCover | null;
  kicker: string;
  genre: string;
  breaking: boolean;
  /** 「日産 公式発表」「日経 報道」 */
  origin: string;
  readMinutes: number;
  /** 発表元のボタンの文字（「日産の発表を読む」）。出典の URL が無ければ出さない */
  sourceCta: string | null;
  sourceUrl: string;
  /** 本文（ノワールの仕上げ済み・3つに分けたもの） */
  body: { top: string; mid: string; tail: string };
  headingsHtml: string;
  calcSlot?: ReactNode;
  priceSlot?: ReactNode;
  /** 比較記事の提携先の一覧（本文の最初の比較表の直後。lib/comparison.ts） */
  compareSlot?: ReactNode;
  slots: {
    /** 要点のすぐ下の「すぐにできること」の短い一覧 */
    quick?: ReactNode;
    /** 上の帯（サイトの速報の1行の代わり）: 同じジャンルの新着1本 */
    genreLine?: ReactNode;
    /** 要点のすぐ下の答えの表（lib/answer-table.ts） */
    answer?: ReactNode;
    /** 要点の下の「この話の続き」（同じ話題の記事2本。components/noir/StoryLinks.tsx） */
    story?: ReactNode;
    /** 本文の最初の章の後ろの「あなたは対象？」（content/next_steps.json） */
    check?: ReactNode;
    /** 本文の直後の「次に読む記事」（2026-11-10 オーナー承認。以前は記事の終わりの出典の後ろ） */
    next?: ReactNode;
    /** 1つ目の PR（要点・すぐにできることの直後） */
    adEarly?: ReactNode;
    afterSummary?: ReactNode;
    adTop?: ReactNode;
    readingMode?: ReactNode;
    easy?: ReactNode;
    inlineRead?: ReactNode;
    adMid?: ReactNode;
    /** 2つ目の PR（本文の途中） */
    adMidPr?: ReactNode;
    /** 本文の途中に挟む欄（不安Q&A・判断ガイド） */
    midBoxes?: ReactNode;
    beforeTail?: ReactNode;
    betweenTail?: ReactNode;
    tailCta?: ReactNode;
    afterBody?: ReactNode;
    afterSource?: ReactNode;
    end?: ReactNode;
    /** 3つ目の PR（記事の終わり・関連記事の前） */
    adEnd?: ReactNode;
    /** PC の右の列（追従） */
    rail?: ReactNode;
    mobileBar?: ReactNode;
  };
  crumbs: { href: string; label: string }[];
  related: ArticleSummary[];
  byline: ReactNode;
};

export default function NoirArticle(props: NoirProps) {
  const { article, title, cover, body, slots } = props;
  const line = article.summaryLine || stripListNumber(article.highlights[0] ?? "");
  const sum = line ? splitEmphasis(line) : null;
  // 要点の1文の下に、残りの要点（同じ内容の言い直しは外す）
  const flat = (t: string) => t.replace(/\*\*|\s|。$/g, "");
  const points = (article.highlights ?? [])
    .map((h) => stripListNumber(h).replace(/\*\*/g, ""))
    .filter((h) => h && (!line || (flat(h) !== flat(line) && !flat(line).includes(flat(h)) && !flat(h).includes(flat(line)))))
    .slice(0, 3);
  // 箱は、意味が伝わり上の1文に無い数字のときだけ（lib/noir.ts の noirKeyFigure。2026-11-07 オーナー）
  const fig = noirKeyFigure(article, line);
  const glyphs = displayGlyphs([title, props.kicker, line, fig ? `${fig.value}${fig.unit}${fig.before ?? ""}` : "", props.headingsHtml, "関連記事よく読まれている記事すぐにできること"]);
  const fontHref = noirFontHref(glyphs);
  const photo = cover?.src ?? null;
  const panel = cover?.kind === "panel";
  const focus = cover?.kind === "official" && article.imageFocus && article.imageFocus.src === article.thumbnail ? article.imageFocus : null;
  // 写真の下の注記: 表紙用の AI のイメージは coverCredit、ほかは記事の写真の出典（公式・素材・AI）
  const creditOf = cover?.kind === "ai" ? article.coverCredit : article.imageCredit;
  const aiShown = cover?.kind === "ai" || (cover && article.imageCredit?.kind === "ai");
  const coverOnTop = cover?.kind === "official";
  const announced = announcedAt(article);
  const dates = bylineDates(article);
  const coverProps = { article, title, cover, photo, panel, focus, creditOf, aiShown: Boolean(aiShown), priority: coverOnTop };

  return (
    <div className="noir" data-layout="noir">
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(props.jsonLd) }} />
      <NoirFonts href={fontHref} />
      <NoirChrome fontHref={fontHref} />
      {slots.genreLine}

      <div className="nr-wrap">
        <div className="nr-main">
          {/* 上のパンくずはジャンルまで（発信元の長い名前で2行になり、答えを押し下げていた。全部は下のパンくずに。2026-11-10） */}
          <nav aria-label="パンくず" className="nr-crumbs nr-crumbs-top">
            <Link href="/">ホーム</Link>
            {props.crumbs.slice(0, 1).map((c) => (
              <span key={c.href} className="contents">
                <span aria-hidden>›</span>
                <Link href={c.href}>{c.label}</Link>
              </span>
            ))}
          </nav>

          <header className="nr-head" id="nr-hero" data-cover={cover?.kind ?? "none"}>
            <div className="nr-kick">
              {props.breaking && <i data-allow-small="">速報</i>}
              {props.genre && <b>{props.genre}</b>}
              {props.kicker && <span>{props.kicker}</span>}
            </div>
            <h1>{title}</h1>
            <div className="nr-meta">
              <span className="nr-origin">{props.origin}</span>
              {/* 署名（2026-11-10 Google Discover・ニュースの準備）: 編集した媒体（/about へ）と、公開・更新の日付と時刻。
                  時刻は構造化データの datePublished・dateModified と同じ（lib/byline.ts）。人が確かめたとは書かない */}
              <span className="nr-byline" data-byline>
                編集：<Link href="/about" rel="author">{siteConfig.author}</Link>
              </span>
              {dates && (
                <span data-byline-dates>
                  公開 <time dateTime={dates.published}>{dates.publishedLabel}</time>
                </span>
              )}
              {dates?.updated && (
                <span>
                  更新 <time dateTime={dates.updated}>{dates.updatedLabel}</time>
                </span>
              )}
              {/* 発表は元の発表の時刻が分かる記事だけ。掲載より後には見せない（SEO A5・lib/articles.ts announcedAt） */}
              {announced && formatDate(announced) && <time dateTime={announced}>発表 {formatDate(announced)}</time>}
              <span>読了 {props.readMinutes}分</span>
            </div>
          </header>

          {/* 表紙の写真（16:9・高さを先に確保して読み込みでずれない）。本物の写真が無い記事は出さない。
              公式の写真だけ題名の下。AI のイメージ・素材・バナーは、答え（要点）・すぐにできること・この話の続きの後ろに置く
              （2026-11-10 オーナー承認: Threads から来た人の最初の画面が、関係の薄い写真で埋まり答えが2画面目だった） */}
          {coverOnTop && <CoverFigure {...coverProps} />}

          {/* 2026-11-11 オーナー決定（台帳 W40）「広告の表示は『PR』だけ。全部で」: ページ冒頭の「本ページはプロモーションを含みます」は出さない。広告の枠ごとの「PR」の札で示す */}

          {(sum || fig) && (
            <section className="nr-sum" aria-label="要点">
              {sum && (
                <div className="nr-srow nr-s1">
                  <p>
                    {sum.before}
                    {sum.em && <em>{sum.em}</em>}
                    {sum.after}
                  </p>
                  {points.length > 0 && (
                    <ul className="nr-points">
                      {points.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              {fig && (
                <div className="nr-srow nr-s2">
                  <div className="nr-big">
                    <b>{fig.value}</b>
                    <i>{fig.unit}</i>
                  </div>
                  {fig.label && <p>{fig.label}</p>}
                  {fig.before && (
                    <div className="nr-was">
                      <span>これまで</span>
                      <s>{fig.before}</s>
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          {/* 答えの表（早見表など。本文の最初の2章の表を要点のすぐ下へ。lib/answer-table.ts。2026-11-11 オーナー「弱点になるなら全部改善して」・読者目線レビュー 3位） */}
          {slots.answer}
          {slots.quick}
          {/* 1つ目の PR（記事に合うものだけ）は答え（要点・答えの表・すぐにできること）のすぐ下（2026-11-11 オーナー: 答えを先に、広告は答えの直後で上のほうに） */}
          {slots.adEarly && <div className="nr-ad nr-ad-early">{slots.adEarly}</div>}
          {slots.story}
          {/* AI のイメージ・素材の写真は、答え・1つ目の PR・この話の続きの後ろ（Discover・SNS の画像には今までどおり使う） */}
          {!coverOnTop && <CoverFigure {...coverProps} />}
          {slots.afterSummary}
          {slots.adTop}
          {slots.readingMode}

          <div id="article-flow" data-read-mode="expert">
            {slots.easy}
            <div className="read-expert" id="nr-body">
              <ArticleProse className="prose nr-prose" html={body.top} slot={props.calcSlot} priceSlot={props.priceSlot} compareSlot={props.compareSlot} />
              {slots.check}
              {body.mid && slots.inlineRead}
              {body.mid && slots.adMid}
              {body.mid && <ArticleProse className="prose nr-prose" html={body.mid} slot={props.calcSlot} priceSlot={props.priceSlot} compareSlot={props.compareSlot} />}
              {/* 2つ目の PR は本文の途中の章の後ろ（途中の章が無い短い記事は、1つ目と並ばないよう判断ガイド・不安Q&A の後ろ） */}
              {body.mid && slots.adMidPr && <div className="nr-ad nr-ad-mid">{slots.adMidPr}</div>}
              {slots.midBoxes}
              {!body.mid && slots.adMidPr && <div className="nr-ad nr-ad-mid">{slots.adMidPr}</div>}
              {body.tail && slots.beforeTail}
            </div>
            {body.tail && slots.betweenTail}
            {body.tail && (
              <div className="read-expert">
                {slots.tailCta}
                <ArticleProse className="prose nr-prose" html={body.tail} slot={props.calcSlot} priceSlot={props.priceSlot} compareSlot={props.compareSlot} />
              </div>
            )}
          </div>

          {props.sourceCta && props.sourceUrl && (
            <a className="nr-srcbtn" href={props.sourceUrl} target="_blank" rel="noopener">
              {props.sourceCta}
              <span aria-hidden>→</span>
            </a>
          )}

          {slots.next}
          {slots.afterBody}
          {slots.adEnd && <div className="nr-ad nr-ad-end">{slots.adEnd}</div>}
          {slots.afterSource}

          {props.related.length > 0 && (
            <section aria-labelledby="related-heading">
              {/* 記事の外側の欄の見出しは h2 にしない（SEO A20） */}
              <p id="related-heading" className="nr-h2">
                関連記事
              </p>
              <div className="nr-rel">
                {props.related.map((item) => (
                  <Link key={item.slug} href={`/articles/${item.slug}`}>
                    <span>
                      <b>{item.title}</b>
                      <small>
                        {item.genre} ・ {formatDate(item.publishedAt)}
                      </small>
                    </span>
                    <i className="nr-ph" aria-hidden>
                      <RelThumb article={item} sizes="96px" />
                    </i>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* メルマガ・通知・タグ・AI の説明は、次に読む記事と関連記事の後ろ（2026-11-10 オーナー承認） */}
          {slots.end}

          <div className="nr-src">{props.byline}</div>
        </div>

        {slots.rail && (
          <aside className="nr-aside" aria-label="おすすめと人気の記事">
            <div className="nr-sticky">{slots.rail}</div>
          </aside>
        )}
      </div>
      {slots.mobileBar}
    </div>
  );
}

type CoverProps = {
  article: FullArticle;
  title: string;
  cover: NoirCover | null;
  photo: string | null;
  panel: boolean;
  focus: { x: number; y: number } | null | undefined;
  creditOf: FullArticle["imageCredit"];
  aiShown: boolean;
  priority: boolean;
};

/** 表紙の写真（題名の下か、要点の後ろ）。AI のイメージには写真の上に必ず札を出す */
function CoverFigure({ article, title, cover, photo, panel, focus, creditOf, aiShown, priority }: CoverProps) {
  return (
    <>
          {photo && (
            <figure className={`nr-cover${panel ? " nr-cover-panel" : ""}${priority ? "" : " nr-cover-low"}`}>
              <div className="nr-cover-img">
                {panel && (
                  <span className="nr-pbg" aria-hidden>
                    <Thumb src={photo} alt="" fill sizes="(min-width: 1024px) 760px, 100vw" className="object-cover" />
                  </span>
                )}
                <Thumb
                  src={photo}
                  alt={title}
                  fill
                  priority={priority}
                  sizes="(min-width: 1024px) 760px, 100vw"
                  className={panel ? "object-contain" : "object-cover"}
                  style={panel ? undefined : { objectPosition: focus ? `${Math.round(focus.x * 100)}% ${Math.round(focus.y * 100)}%` : "50% 40%" }}
                />
                {/* AI のイメージには、写真の上に必ず札を出す（本物の写真と受け取られないように。台帳 I4）。
                    2026-11-11 オーナー承認: 札は小さく右下の角に「イメージ（AI生成）」だけ。発表の札・長い説明は写真の下の注記（ImageCredit） */}
                {aiShown && (
                  <span className="nr-ailabel ai-tag" data-ai-tag="" data-allow-small="">
                    {NOIR_AI_TAG}
                  </span>
                )}
              </div>
              <figcaption>
                <ImageCredit credit={creditOf} />
              </figcaption>
            </figure>
          )}

    </>
  );
}
