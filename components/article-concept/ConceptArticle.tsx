import { Noto_Sans_JP } from "next/font/google";
import type { CSSProperties } from "react";
import RelTime from "@/components/RelTime";
import type { AffiliateLink } from "@/lib/articles";
import { siteConfig } from "@/site.config";
import Expand from "./Expand";
import type { ConceptView } from "./view";
import "./concept.css";

// 表紙（報道テロップ型）と同じ書体。この試作ページだけで読み込む
const noto = Noto_Sans_JP({ weight: "variable", subsets: ["latin"], display: "swap", preload: false, variable: "--font-cx" });

type Props = { view: ConceptView; affiliates: AffiliateLink[] };

/**
 * 「引き算のAI」記事ページ（試作）。
 * 長い記事をAIが読み、要らないものを削って残った1枚。最初は結論1文と要点3つだけを大きく置き、
 * 「もっと詳しく」1つで 1分版 → 全文 とその場で伸びる。
 */
export default function ConceptArticle({ view, affiliates }: Props) {
  const style = {
    "--co": view.company.color,
    // 写真が無いときの地色（企業が判別できない記事は墨）
    "--co-field": view.company.isOther ? "#1d1d22" : view.company.color,
    // 番号・下線の色。企業が判別できない記事は赤（速報・続報の色）と混ざらないよう墨にする
    ...(view.company.isOther ? { "--co-accent": "var(--cx-ink)" } : {}),
  } as CSSProperties;
  const ghost = view.company.name || view.source.name;

  return (
    <article className={`cx ${noto.variable}`} style={style}>
      {/* 表紙と同じ型：写真はそのまま、下だけ暗く、企業色の縦線と赤いラベル */}
      <header className={`cx-hero ${view.photo ? "has-photo" : "no-photo"}`}>
        {view.photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="cx-hero-photo" src={view.photo} alt="" decoding="async" fetchPriority="high" />
        ) : (
          <span className="cx-hero-ghost" aria-hidden>
            {ghost}
          </span>
        )}
        <div className="cx-hero-inner">
          <span className="cx-hero-bar" aria-hidden />
          <div className="cx-hero-text">
            <p className="cx-hero-label">
              <span className="cx-flash">{view.label}</span>
              <span>{view.company.name || view.source.name}</span>
            </p>
            <h1 className="cx-title">{view.title}</h1>
          </div>
        </div>
      </header>

      <div className="cx-sheet">
        {/* 欄外：出典・発表日・経過時間・公式へのリンク（PCは左の欄、スマホは結論の上の1行） */}
        <aside className="cx-margin" aria-label="出典">
          <p className="cx-source">{view.source.name}</p>
          <p className="cx-dates">
            {view.publishedLabel && <span>{view.publishedLabel} 発表</span>}
            <span>
              {view.stampPrefix} <RelTime iso={view.stampIso} />
            </span>
          </p>
          {view.source.href && (
            <a className="cx-official" href={view.source.href} target="_blank" rel="noopener noreferrer">
              {view.source.cta}
            </a>
          )}
          <p className="cx-cut">
            全文 <b>{view.bodyChars.toLocaleString("ja-JP")}</b>字 → <b>3</b>行
          </p>
        </aside>

        <div className="cx-main">
          <p className="mb-4 mt-4 flex flex-wrap gap-x-5 gap-y-1 text-note leading-relaxed text-[var(--cx-ink-2)] lg:mt-0">
            <span>
              制作：<a href="/about" rel="author" className="font-semibold underline underline-offset-4">{siteConfig.author}</a>
            </span>
            <a href="/editorial-policy" className="underline underline-offset-4">編集方針・AI利用と事実確認</a>
          </p>
          {/* 物語の線：続報がある記事だけ。細い1本の線 */}
          {view.timeline.length > 0 && (
            <ol className="cx-story" aria-label="この話の流れ">
              {view.timeline.map((event, i) => (
                <li key={`${event.date}-${i}`} className={i === view.timeline.length - 1 ? "is-now" : ""}>
                  {event.target ? (
                    <a href={`#${event.target}`}>
                      <span className="cx-story-date">{event.date}</span>
                      <span className="cx-story-label">{event.label}</span>
                    </a>
                  ) : (
                    <span>
                      <span className="cx-story-date">{event.date}</span>
                      <span className="cx-story-label">{event.label}</span>
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}

          {/* 10秒版：結論1文と要点3つだけ */}
          <p className="cx-conclusion">{view.conclusion}</p>
          <ol className="cx-points">
            {view.points.map((html, i) => (
              <li key={i}>
                <span className="cx-point-n" aria-hidden>
                  {i + 1}
                </span>
                <span dangerouslySetInnerHTML={{ __html: html }} />
              </li>
            ))}
          </ol>
          {view.fit.length > 0 && (
            <p className="cx-fit">
              {view.fit.map((part) => (
                <span key={part}>{part}</span>
              ))}
            </p>
          )}
        </div>

        <div className="cx-more-area">
          <Expand
            minuteLabel={`${view.minuteMinutes}分`}
            fullLabel={`全文 ${view.fullMinutes}分`}
            minute={
              <>
                <p className="cx-stage-label">
                  <span>1分版</span>
                </p>
                <div className="cx-prose cx-minute" dangerouslySetInnerHTML={{ __html: view.minuteHtml }} />
              </>
            }
            full={
              <div className="cx-full">
                <p className="cx-stage-label">
                  <span>全文</span>
                </p>
                {view.sections.map((section) => (
                  <section key={section.id} className={`cx-sec${section.update ? " is-update" : ""}`} aria-labelledby={section.id}>
                    <h2 id={section.id} className="cx-q">
                      <span className="cx-q-text">{section.question}</span>
                      {section.update && (
                        <span className="cx-q-note">
                          {section.update}　{section.original}
                        </span>
                      )}
                    </h2>
                    <div className="cx-prose" dangerouslySetInnerHTML={{ __html: section.html }} />
                  </section>
                ))}
                {/* 広告・提携リンクは本番でも全文の後ろだけに置く（10秒版・1分版には出さない） */}
                {affiliates.length > 0 && (
                  <section className="cx-sec cx-pr" aria-label="関連サービス（PR）">
                    <h2 className="cx-q">
                      <span className="cx-q-text">試すなら</span>
                      <span className="cx-q-note">PR</span>
                    </h2>
                    <ul className="cx-pr-list">
                      {affiliates.map((link) => (
                        <li key={link.url}>
                          <a href={link.url} target="_blank" rel="sponsored nofollow noopener noreferrer">
                            {link.label || link.name}
                          </a>
                          {link.note && <span className="cx-pr-note">{link.note}</span>}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            }
          />
        </div>

        <footer className="cx-foot">
          <p>
            出典：{view.source.name}
            {view.source.href && (
              <>
                {" "}
                <a href={view.source.href} target="_blank" rel="noopener noreferrer">
                  {view.source.cta}
                </a>
              </>
            )}
          </p>
          {view.disclaimer && <p className="cx-disclaimer">{view.disclaimer}</p>}
        </footer>
      </div>
    </article>
  );
}
