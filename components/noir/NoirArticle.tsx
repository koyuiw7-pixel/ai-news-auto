import type { ReactNode } from "react";
import Link from "next/link";
import Thumb from "@/components/Thumb";
import ArticleProse from "@/components/ArticleProse";
import NoirChrome from "@/components/noir/NoirChrome";
import NoirFonts, { noirFontHref } from "@/components/noir/NoirFonts";
import { formatDate, type ArticleSummary, type FullArticle } from "@/lib/articles";
import { officialCreditText } from "@/lib/image-credit";
import { displayGlyphs, splitEmphasis } from "@/lib/noir";
import { stripListNumber } from "@/lib/list-number";
import "./noir.css";

/**
 * 新しい記事の見た目「ノワール」（2026-11-07 オーナー承認・台帳 W36）。layout が "noir" の記事だけ。
 * 黒い表紙（公式の写真を全面に。無ければ題名を大きく）→ 白い紙面（要点の1文・大きな数字・本文・まとめ・発表元のボタン）→ 関連記事。
 * 見出し・構造化データ・広告・提携・計測・オーナーのルールの部品は、今までの記事ページ（app/articles/[slug]/page.tsx）で作った物をそのまま受け取って並べる。
 * 「このニュースを3行で」「何が起きた」「KEY NUMBERS」のような決まった型の見出しは付けない（オーナーが AI っぽいと判断）。
 */
export type NoirProps = {
  article: FullArticle;
  title: string;
  jsonLd: unknown;
  photo: string | null;
  kicker: string;
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
  slots: {
    afterSummary?: ReactNode;
    adTop?: ReactNode;
    readingMode?: ReactNode;
    easy?: ReactNode;
    inlineRead?: ReactNode;
    adMid?: ReactNode;
    beforeTail?: ReactNode;
    betweenTail?: ReactNode;
    tailCta?: ReactNode;
    afterBody?: ReactNode;
    afterSource?: ReactNode;
    end?: ReactNode;
    rail?: ReactNode;
    mobileBar?: ReactNode;
  };
  crumbs: { href: string; label: string }[];
  related: ArticleSummary[];
  byline: ReactNode;
};

export default function NoirArticle(props: NoirProps) {
  const { article, title, photo, body, slots } = props;
  const line = article.summaryLine || stripListNumber(article.highlights[0] ?? "");
  const sum = line ? splitEmphasis(line) : null;
  const fig = article.keyFigure && article.keyFigure.value ? article.keyFigure : null;
  const glyphs = displayGlyphs([title, props.kicker, line, fig ? `${fig.value}${fig.unit}${fig.before ?? ""}` : "", props.headingsHtml, ...props.related.map((r) => r.title), "関連記事"]);
  const fontHref = noirFontHref(glyphs);
  const focus = article.imageFocus && article.imageFocus.src === article.thumbnail ? article.imageFocus : null;
  // 写真を出すのは公式発表の写真だけなので、注記も「写真：〇〇」の1行（lib/image-credit.ts）
  const credit = photo ? officialCreditText(article.imageCredit) : null;

  return (
    <div className="noir" data-layout="noir">
      <script type="application/ld+json" suppressHydrationWarning dangerouslySetInnerHTML={{ __html: JSON.stringify(props.jsonLd) }} />
      <NoirFonts href={fontHref} />
      <NoirChrome fontHref={fontHref} />
      <span className="nr-safe" aria-hidden />
      {/* 上の帯は表紙（黒・写真）の上に重なる。文字の見やすさの点検は親の背景（白い紙）で測ってしまうので対象外の印を付ける。
          実際の見え方: 表紙の上は白い文字、表紙を過ぎると白い帯に黒い文字（どちらも 4.5:1 以上） */}
      <div className="nr-top nr-g" id="nr-top" data-decorative="">
        <Link href="/" className="nr-logo" aria-label="サイソクニュース トップへ">
          サイソク
        </Link>
        <span className="nr-t" aria-hidden>
          {title}
        </span>
        <i className="nr-bar" id="nr-bar" aria-hidden />
      </div>

      <header className={`nr-hero${photo ? "" : " nr-type"}`} id="nr-hero">
        {photo && (
          <div className="nr-img" id="nr-img">
            <Thumb
              src={photo}
              alt=""
              fill
              priority
              sizes="100vw"
              className="object-cover"
              style={{ objectPosition: focus ? `${Math.round(focus.x * 100)}% ${Math.round(focus.y * 100)}%` : "50% 40%" }}
            />
          </div>
        )}
        <div className="nr-hl nr-g">
          <div className="nr-col">
            {!photo && <span className="nr-rule" aria-hidden />}
            <div className="nr-kick">
              {props.breaking && <i data-allow-small="">速報</i>}
              <span>{props.kicker}</span>
            </div>
            <h1>{title}</h1>
            <div className="nr-meta">
              <span>{props.origin}</span>
              <time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time>
              {article.generatedAt && <span>掲載 {formatDate(article.generatedAt)}</span>}
              <span>読了 {props.readMinutes}分</span>
              {article.updatedAt && <span>更新 {formatDate(article.updatedAt)}</span>}
            </div>
          </div>
        </div>
      </header>

      <div className="nr-sheet nr-g">
        <div className="nr-col">
          {/* ステマ規制（景品表示法）に沿い、広告を含みうる全記事の冒頭で明示する */}
          <p className="nr-pr">本ページはプロモーションを含みます</p>

          {(sum || fig) && (
            <section className="nr-sum" aria-label="要点">
              {sum && (
                <div className="nr-srow nr-s1">
                  <p>
                    {sum.before}
                    {sum.em && <em>{sum.em}</em>}
                    {sum.after}
                  </p>
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
              <a className="nr-more" href="#nr-body">
                続きを読む <span aria-hidden>↓</span>
              </a>
            </section>
          )}

          {slots.afterSummary}
          {slots.adTop}
          {slots.readingMode}

          <div id="article-flow" data-read-mode="expert">
            {slots.easy}
            <div className="read-expert" id="nr-body">
              <ArticleProse className="prose nr-prose" html={body.top} slot={props.calcSlot} priceSlot={props.priceSlot} />
              {body.mid && slots.inlineRead}
              {body.mid && slots.adMid}
              {body.mid && <ArticleProse className="prose nr-prose" html={body.mid} slot={props.calcSlot} priceSlot={props.priceSlot} />}
              {body.tail && slots.beforeTail}
            </div>
            {body.tail && slots.betweenTail}
            {body.tail && (
              <div className="read-expert">
                {slots.tailCta}
                <ArticleProse className="prose nr-prose" html={body.tail} slot={props.calcSlot} priceSlot={props.priceSlot} />
              </div>
            )}
          </div>

          {props.sourceCta && props.sourceUrl && (
            <a className="nr-srcbtn rv" href={props.sourceUrl} target="_blank" rel="noopener">
              {props.sourceCta}
              <span aria-hidden>→</span>
            </a>
          )}

          {slots.afterBody}
          {slots.afterSource}
          {slots.end}
          {slots.rail && (
            <div className="nr-slot nr-rail" data-dense="">
              {slots.rail}
            </div>
          )}

          {props.related.length > 0 && (
            <section aria-labelledby="related-heading">
              <h2 id="related-heading" className="nr-h2 rv">
                関連記事
              </h2>
              <div className="nr-rel rv">
                {props.related.map((item) => (
                  <Link key={item.slug} href={`/articles/${item.slug}`}>
                    <span>
                      <b>{item.title}</b>
                      <small>
                        {item.genre} ・ {formatDate(item.publishedAt)}
                      </small>
                    </span>
                    <i className="nr-ph" aria-hidden>
                      {item.thumbnail && item.imageCredit?.kind !== "ai" && (
                        <Thumb src={item.thumbnail} alt="" fill sizes="84px" className="object-cover" />
                      )}
                    </i>
                  </Link>
                ))}
              </div>
            </section>
          )}

          <div className="nr-src">
            {props.byline}
            {credit && <p>{credit}</p>}
            <nav aria-label="パンくず" className="nr-crumbs">
              <Link href="/">ホーム</Link>
              {props.crumbs.map((c) => (
                <span key={c.href} className="contents">
                  <span aria-hidden>/</span>
                  <Link href={c.href}>{c.label}</Link>
                </span>
              ))}
            </nav>
          </div>
        </div>
      </div>
      {slots.mobileBar}
    </div>
  );
}
