import { BIZ_UDPGothic, Noto_Sans_JP } from "next/font/google";
import VerdictCard from "@/components/VerdictCard";
import VerdictIcon from "@/components/VerdictIcon";
import { STATUS_LABEL, freeLabel, japanLabel, usability } from "@/lib/verdict";
import PreviewArticle from "./PreviewArticle";
import { TocFloat, TocRail } from "./TocClient";
import { emphasizeFigures, type ArticleView } from "./view";

// 案ごとの本文書体（確認用ページだけで読み込む）
const noto = Noto_Sans_JP({ weight: "variable", subsets: ["latin"], display: "swap", preload: false, variable: "--font-ap-noto" });
const bizud = BIZ_UDPGothic({ weight: ["400", "700"], subsets: ["latin"], display: "swap", preload: false, variable: "--font-ap-ud" });

function judgedAt(view: ArticleView) {
  return view.verdict?.judgedAt || view.article.generatedAt || view.article.publishedAt;
}

/* ===================================================================== */
/* A：読みやすさ重視・控えめ                                               */
/* ===================================================================== */

export function VariantA({ view }: { view: ArticleView }) {
  const [lead, ...rest] = view.article.highlights;
  return (
    <PreviewArticle
      view={view}
      slots={{
        className: "ap-a",
        summary: (
          <>
            {lead && (
              <section aria-labelledby="a-points" className="mt-6 rounded-2xl border border-line-strong bg-paper">
                <div className="px-5 pt-5 sm:px-7 sm:pt-6">
                  <h2 id="a-points" className="text-meta font-bold tracking-[0.08em] text-muted">
                    {view.article.highlights.length}行でわかる
                  </h2>
                  <p
                    className="ap-lead mt-2 text-[1.2rem] font-bold leading-[1.7] text-ink sm:text-[1.35rem]"
                    dangerouslySetInnerHTML={{ __html: emphasizeFigures(lead) }}
                  />
                </div>
                {rest.length > 0 && (
                  <ul className="mt-4 grid gap-2.5 border-t border-line px-5 py-4 sm:px-7">
                    {rest.map((text) => (
                      <li key={text} className="grid grid-cols-[14px_1fr] gap-2.5 text-desc font-medium leading-[1.75] text-ink-soft">
                        <span aria-hidden className="mt-[0.7em] h-[2px] w-[10px] bg-ink-soft" />
                        <span dangerouslySetInnerHTML={{ __html: emphasizeFigures(text) }} />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
            {view.verdict && <VerdictCard verdict={view.verdict} judgedAt={judgedAt(view)} />}
          </>
        ),
        topToc:
          view.headings.length > 1 ? (
            <details className="ap-toc-a group mt-8 rounded-2xl border border-line">
              <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-3.5 text-note font-bold text-ink">
                目次
                <span className="index-num text-meta font-normal text-muted">
                  全{view.headings.length}章・約{view.readMinutes}分
                </span>
                <span aria-hidden className="ml-auto text-muted transition-transform group-open:rotate-180">▾</span>
              </summary>
              <ol className="grid gap-0.5 border-t border-line px-3 py-3 sm:grid-cols-2 sm:gap-x-4">
                {view.headings.map((h, i) => (
                  <li key={h.id}>
                    <a href={`#${h.id}`} className="grid grid-cols-[1.75rem_1fr] rounded-lg px-2 py-1.5 text-note leading-snug text-ink-soft hover:bg-surface hover:text-ink">
                      <span className="index-num text-meta text-muted">{i + 1}</span>
                      {h.text}
                    </a>
                  </li>
                ))}
              </ol>
            </details>
          ) : undefined,
      }}
    />
  );
}

/* ===================================================================== */
/* B：ニュース番組型（テロップ）                                            */
/* ===================================================================== */

function TelopRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid border-t border-line first:border-t-0 sm:grid-cols-[7.5rem_1fr]">
      <div className="flex items-start px-4 pt-4 sm:px-5 sm:py-4">
        <span className="bg-ink px-2 py-0.5 text-meta font-bold tracking-[0.08em] text-paper">{label}</span>
      </div>
      <div className="px-4 pb-4 pt-2 sm:px-5 sm:py-4">{children}</div>
    </div>
  );
}

export function VariantB({ view }: { view: ArticleView }) {
  const { verdict, stats } = view;
  const conclusion = verdict?.take || view.article.highlights[0] || view.article.description;
  const changes = verdict ? stats : stats.slice(1);
  return (
    <PreviewArticle
      view={view}
      slots={{
        className: `ap-b ${noto.variable}`,
        summary: (
          <section aria-labelledby="b-sum" className="mt-6 overflow-hidden border-2 border-ink">
            <div className="flex items-stretch text-meta font-bold">
              <span className="bg-live px-3 py-1.5 tracking-[0.12em] text-white">要点</span>
              <h2 id="b-sum" className="flex-1 bg-ink px-3 py-1.5 text-paper">このニュースを30秒で</h2>
              {verdict && (
                <span className="flex items-center gap-1.5 bg-paper px-3 text-ink">
                  <VerdictIcon kind={usability(verdict)} size={14} />
                  {STATUS_LABEL[verdict.status]}
                </span>
              )}
            </div>
            <TelopRow label="結論">
              <p className="text-[1.15rem] font-black leading-[1.6] text-ink sm:text-[1.3rem]" dangerouslySetInnerHTML={{ __html: emphasizeFigures(conclusion) }} />
            </TelopRow>
            {changes.length > 0 && (
              <TelopRow label="何が変わる">
                <ul className="grid gap-3">
                  {changes.map((s) => (
                    <li key={s.text} className={`grid items-baseline gap-x-4 gap-y-0.5 ${s.value ? "sm:grid-cols-[minmax(7.5rem,auto)_1fr]" : ""}`}>
                      {s.value && <span className="ap-bignum index-num text-[1.6rem] font-semibold leading-none tracking-tight text-ink">{s.value}</span>}
                      <span className="text-desc font-medium leading-[1.75] text-ink-soft">{s.text}</span>
                    </li>
                  ))}
                </ul>
              </TelopRow>
            )}
            {verdict && (
              <TelopRow label="誰に関係">
                {verdict.audience && <p className="text-[16px] font-bold text-ink">{verdict.audience}</p>}
                <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-meta">
                  <div className="flex gap-1.5"><dt className="text-muted">日本</dt><dd className="font-bold text-ink">{japanLabel(verdict)}</dd></div>
                  <div className="flex gap-1.5"><dt className="text-muted">料金</dt><dd className="index-num font-bold text-ink">{verdict.price || "不明"}</dd></div>
                  <div className="flex gap-1.5"><dt className="text-muted">無料</dt><dd className="font-bold text-ink">{freeLabel(verdict.free)}</dd></div>
                </dl>
              </TelopRow>
            )}
          </section>
        ),
        railToc: view.headings.length > 1 ? <TocRail headings={view.headings} minutes={view.readMinutes} /> : undefined,
        topToc:
          view.headings.length > 1 ? (
            <nav aria-label="目次" className="mt-8 border-y-2 border-ink py-3 xl:hidden">
              <p className="text-meta font-bold tracking-[0.1em] text-muted">目次・全{view.headings.length}章</p>
              <ol className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                {view.headings.map((h, i) => (
                  <li key={h.id}>
                    <a href={`#${h.id}`} className="text-note font-bold text-ink hover:underline">
                      <span className="index-num mr-1 text-meta font-normal text-muted">{String(i + 1).padStart(2, "0")}</span>
                      {h.text}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          ) : undefined,
      }}
    />
  );
}

/* ===================================================================== */
/* C：要点ファースト・図解                                                 */
/* ===================================================================== */

const ICONS: { test: RegExp; path: string }[] = [
  { test: /価格|料金|コスト|円|ドル|\$|安/, path: "M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" },
  { test: /速|高速|時間|短縮/, path: "M13 2 3 14h9l-1 8 10-12h-9l1-8z" },
  { test: /精度|誤|ハルシネーション|正確|エラー/, path: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" },
  { test: /操作|PC|画面|エージェント|自動/, path: "M3 4h18v12H3zM8 20h8M12 16v4" },
  { test: /日本|提供|利用|公開|発表/, path: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20" },
];
const DEFAULT_ICON = "M3 3v18h18M7 15l4-4 3 3 5-6";

function PointIcon({ text }: { text: string }) {
  const path = ICONS.find((i) => i.test.test(text))?.path ?? DEFAULT_ICON;
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={path} />
    </svg>
  );
}

export function VariantC({ view }: { view: ArticleView }) {
  const { verdict, stats } = view;
  const conclusion = verdict?.take || view.article.highlights[0] || view.article.description;
  const points = verdict ? stats : stats.slice(1);
  const kind = verdict ? usability(verdict) : null;
  return (
    <PreviewArticle
      view={view}
      slots={{
        className: `ap-c ${bizud.variable}`,
        floating: <TocFloat headings={view.headings} />,
        summary: (
          <section aria-labelledby="c-sum" className="mt-6">
            <div className="rounded-3xl bg-ink p-5 text-paper sm:p-7">
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="c-sum" className="text-meta font-bold tracking-[0.14em] opacity-70">結論</h2>
                {verdict && kind && (
                  <span className={`ml-auto inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-meta font-bold ${kind === "go" ? "bg-go-soft text-go" : "bg-surface text-ink"}`}>
                    <VerdictIcon kind={kind} size={15} />
                    {STATUS_LABEL[verdict.status]}
                  </span>
                )}
              </div>
              <p className="mt-2 text-[1.2rem] font-bold leading-[1.65] sm:text-[1.4rem]">{conclusion}</p>
              {verdict && (
                <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    ["日本から", japanLabel(verdict)],
                    ["料金", verdict.price || "不明"],
                    ["無料で", freeLabel(verdict.free)],
                    ["向いている人", verdict.audience || "—"],
                  ].map(([k, v]) => (
                    <div key={k} className="rounded-xl bg-paper/10 px-3 py-2">
                      <dt className="text-meta opacity-65">{k}</dt>
                      <dd className="mt-0.5 text-note font-bold leading-snug">{v}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            {points.length > 0 && (
              <ol className="mt-3 grid gap-3 sm:grid-cols-3">
                {points.map((p, i) => (
                  <li key={p.text} className="flex flex-col rounded-2xl border border-line bg-surface p-4">
                    <div className="flex items-center gap-2 text-accent">
                      <span className="grid size-9 place-items-center rounded-xl bg-accent-soft">
                        <PointIcon text={p.text} />
                      </span>
                      <span className="index-num ml-auto text-meta text-muted">POINT {i + 1}</span>
                    </div>
                    {p.value && <p className="index-num mt-3 text-[1.45rem] font-semibold leading-none tracking-tight text-ink">{p.value}</p>}
                    <p className="mt-2 text-[14.5px] font-bold leading-[1.7] text-ink-soft">{p.text}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        ),
        topToc:
          view.headings.length > 1 ? (
            <nav aria-label="この記事の流れ" className="mt-8">
              <p className="text-meta font-bold text-muted">この記事の流れ</p>
              <ol className="ap-flow mt-2">
                {view.headings.map((h, i) => (
                  <li key={h.id}>
                    <a href={`#${h.id}`}>
                      <span className="index-num">{i + 1}</span>
                      {h.text}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          ) : undefined,
      }}
    />
  );
}
