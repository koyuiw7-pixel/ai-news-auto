/**
 * 記事を一歩深くする欄（2026-11-09 オーナー指摘・台帳 A66）。中身は scripts/depth_fields.py が公式ページから作る。
 * どの項目も読んだ公式ページの URL（source）を持ち、数字・「」の名前・URL はそのページにあるものだけ（プログラムで照合済み）。
 *   InsightBox     「なるほど」: 誰でも知っている注意ではなく、公式ページにだけある具体的な事実（記事の上のほう）
 *   CauseBox       「なぜ起きた？」: 公式ページが書く原因・背景。未発表なら「調査中」とはっきり書く
 *   WorriesBlock   「こんな不安ありませんか」: 読者の不安への答えと行動（一般の注意のページが出典のものは札を付ける）
 *   ActionSteps    「すぐにできること」の手順つき版（todayActions の代わりに出す）
 *   DecisionGuide  「判断ガイド」: 乗り換える？番号を変える？などの迷いに、状況→おすすめ→理由→出どころ（中立に。後押しはしない）
 *   OfficialDesk   「公式窓口」: 正式名・電話・受付時間・押せる URL と、そのページへの辿り方の図（画面の写真は使わない。自前の図）
 */
import type React from "react";
import type { Cause, DeskEntry, GuideRow, InsightItem, StepItem, WorryItem } from "@/lib/depth";
import { sourceLabel } from "@/lib/depth";

function SourceLink({ url, general }: { url: string; general?: boolean }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener"
      className="mt-1 inline-block text-meta text-muted underline decoration-line-strong underline-offset-4 hover:text-ink"
    >
      {general ? "一般的な注意・" : "出典・"}
      {sourceLabel(url)}
    </a>
  );
}

/** 欄の見出し: 小さな札（欄の種類）＋記事ごとの見出し（depthHeadings。無い古い記事は札の言葉をそのまま見出しに） */
function BoxHeading({ id, kicker, heading, fallback, size = "t-h2", extra }: {
  id: string; kicker: string; heading?: string; fallback: string; size?: string; extra?: React.ReactNode;
}) {
  return (
    <>
      {heading && <p className="dbx-kick text-badge font-bold tracking-wide text-accent">{kicker}</p>}
      <h2 id={id} className={`${heading ? "mt-1 " : ""}flex flex-wrap items-center gap-2 ${size}`}>
        {heading || fallback}
        {extra}
      </h2>
    </>
  );
}

export function InsightBox({ items, heading }: { items: InsightItem[]; heading?: string }) {
  return (
    <section aria-labelledby="insight-heading" id="insight" className="dbx dbx-insight mb-8 max-w-[40em] rounded-2xl border-2 border-accent bg-accent-soft p-5 sm:p-6">
      <BoxHeading id="insight-heading" kicker="なるほど" heading={heading} fallback="なるほどポイント" size="t-h3" />
      <p className="mt-1 text-meta text-ink-soft">公式ページで確かめた、知っておくと役立つこと</p>
      <ul className="mt-3.5 grid gap-3.5">
        {items.map((item, index) => (
          <li key={index} className="text-desc leading-[1.8] text-ink">
            {item.text}
            <br />
            <SourceLink url={item.source} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CauseBox({ cause, heading }: { cause: Cause; heading?: string }) {
  return (
    <section aria-labelledby="cause-heading" id="cause" className="dbx dbx-cause mt-12 max-w-[40em] rounded-2xl bg-surface p-5 sm:p-6">
      <BoxHeading
        id="cause-heading"
        kicker={cause.status === "background" ? "背景" : "なぜ起きた？"}
        heading={heading}
        fallback={cause.status === "background" ? "なぜ変わる？" : "なぜ起きた？"}
        size="t-h3"
        extra={
          cause.status === "investigating" && (
            <span className="rounded-sm border border-line-strong px-2 py-[1px] text-badge font-bold text-ink-soft">原因は調査中</span>
          )
        }
      />
      <p className="mt-3 text-desc leading-[1.85] text-ink">{cause.text}</p>
      <SourceLink url={cause.source} />
    </section>
  );
}

/**
 * 不安Q&A。extra に記事の「よくある質問」（components/ArticleFaq.tsx と同じ問いと答え）を渡すと、同じ欄の後ろに足す
 * （2026-11-10 オーナー承認: 「不安Q&A」と「よくある質問」がほぼ同じ中身で2回出てページが長かった。ノワールの記事は1つにまとめる）。
 * openCount: はじめから開いておく問いの数
 */
export function WorriesBlock({ items, heading, extra = [], openCount = 2 }: {
  items: WorryItem[]; heading?: string; extra?: { q: string; a: string }[]; openCount?: number;
}) {
  const seen = new Set(items.map((item) => item.q.replace(/[\s？?。]/g, "")));
  const more = extra.filter((row) => !seen.has(row.q.replace(/[\s？?。]/g, "")));
  return (
    <section aria-labelledby="worries-heading" id="worries" className="dbx dbx-worries mt-12 max-w-[40em]">
      <BoxHeading id="worries-heading" kicker="不安Q&A" heading={heading} fallback="こんな不安ありませんか" />
      <div className="mt-4 grid gap-3">
        {items.map((item, index) => (
          <details key={index} className="group rounded-2xl border border-line px-5 py-4 open:border-line-strong" open={index < openCount}>
            <summary className="flex cursor-pointer list-none items-start gap-3 text-desc font-bold leading-snug text-ink">
              <span aria-hidden className="shrink-0 text-accent">Q</span>
              <span className="flex-1">{item.q}</span>
              <span aria-hidden className="shrink-0 text-muted transition-transform group-open:rotate-180">▾</span>
            </summary>
            <div className="mt-2.5 pl-6">
              {item.general && (
                <p className="mb-1.5 inline-block rounded-sm bg-surface px-2 py-[1px] text-badge font-bold text-ink-soft">
                  公式発表に答えが無いため、公的機関の一般的な注意から
                </p>
              )}
              <p className="text-desc leading-[1.8] text-ink-soft">{item.a}</p>
              <SourceLink url={item.source} general={item.general} />
              {item.action && (
                <p className="mt-2.5 rounded-xl bg-go-soft px-3.5 py-2.5 text-desc font-medium leading-[1.75] text-ink">
                  <span className="mr-1.5 font-bold text-go">今できること</span>
                  {item.action}
                  {item.actionSource && (
                    <>
                      <br />
                      <SourceLink url={item.actionSource} general={item.actionGeneral} />
                    </>
                  )}
                </p>
              )}
            </div>
          </details>
        ))}
        {more.map((row, index) => (
          <details key={`faq-${index}`} className="group rounded-2xl border border-line px-5 py-4 open:border-line-strong">
            <summary className="flex cursor-pointer list-none items-start gap-3 text-desc font-bold leading-snug text-ink">
              <span aria-hidden className="shrink-0 text-accent">Q</span>
              <span className="flex-1">{row.q}</span>
              <span aria-hidden className="shrink-0 text-muted transition-transform group-open:rotate-180">▾</span>
            </summary>
            <p className="mt-2.5 pl-6 text-desc leading-[1.8] text-ink-soft">{row.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

/**
 * 開け閉めできる欄（2026-11-10 オーナー承認: 公式窓口・判断ガイド・手順は見出しだけ出し、押すと中身が出る。ページの長さを半分に）。
 * 閉じた状態がはじめの形なので、読み込みで画面がずれない。JS が無くても開く（details）。
 * 「#steps」などへのリンクで飛んだときは components/noir/FoldOpener.tsx が開く。
 */
export function Fold({ id, kicker, title, note, children }: { id?: string; kicker: string; title: string; note?: string; children: React.ReactNode }) {
  return (
    <details id={id} className="dbx-fold group mt-10 max-w-[40em] rounded-2xl border border-line-strong">
      <summary className="flex min-h-14 cursor-pointer list-none items-center gap-3 px-5 py-3.5">
        <span className="min-w-0 flex-1">
          <span className="block text-badge font-bold tracking-wide text-accent">{kicker}</span>
          <span className="mt-0.5 block text-desc font-bold leading-snug text-ink">{title}</span>
          {note && <span className="mt-0.5 block text-meta text-muted">{note}</span>}
        </span>
        <span className="shrink-0 rounded-full border border-line-strong px-3 py-1 text-meta font-bold text-ink">
          <span className="group-open:hidden">開く</span>
          <span className="hidden group-open:inline">閉じる</span>
        </span>
      </summary>
      <div className="border-t border-line px-5 pb-5 [&>section:first-child]:mt-4">{children}</div>
    </details>
  );
}

export function ActionSteps({ items, heading }: { items: StepItem[]; heading?: string }) {
  return (
    <section aria-labelledby="today-actions-heading" id="steps" className="dbx dbx-steps mt-12 max-w-[40em] rounded-2xl border border-line-strong p-5 sm:p-6">
      <BoxHeading id="today-actions-heading" kicker="すぐにできること" heading={heading} fallback="すぐにできること" size="t-h3" />
      <ol className="mt-3.5 grid gap-4">
        {items.map((item, index) => (
          <li key={index} className="grid grid-cols-[24px_1fr] gap-3">
            <span className="index-num mt-0.5 grid size-6 place-items-center rounded-full bg-ink text-meta font-semibold text-paper">
              {index + 1}
            </span>
            <div>
              <p className="text-desc font-bold leading-[1.7] text-ink">{item.action}</p>
              {item.steps && item.steps.length > 0 && (
                <ol className="mt-1.5 grid gap-1 border-l-2 border-line pl-3">
                  {item.steps.map((step, i) => (
                    <li key={i} className="text-note leading-[1.7] text-ink-soft">
                      <span className="mr-1 font-bold text-ink">{`${index + 1}-${i + 1}`}</span>
                      {step}
                    </li>
                  ))}
                </ol>
              )}
              {item.url && (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener"
                  className="mt-2 inline-flex min-h-10 items-center gap-1 rounded-full border border-line-strong px-3.5 text-note font-bold text-ink hover:bg-surface"
                >
                  公式ページを開く <span className="font-medium text-muted">{sourceLabel(item.url)}</span>
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** 辿り方の図（自前の図。トップ → メニュー → 目的のページ の段を、矢印でつないだ箱で描く。スマホでは折り返す） */
function RouteFigure({ steps, label }: { steps: string[]; label: string }) {
  return (
    <figure className="mt-3" aria-label={`${label}への辿り方`}>
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
        {steps.map((step, i) => (
          <li key={i} className="flex items-center gap-1.5">
            <span
              className={`rounded-lg border px-2.5 py-1.5 text-meta font-bold leading-tight ${
                i === steps.length - 1 ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-paper text-ink"
              }`}
            >
              <span className="mr-1 opacity-70">{i + 1}</span>
              {step}
            </span>
            {i < steps.length - 1 && (
              <span aria-hidden className="text-muted">
                →
              </span>
            )}
          </li>
        ))}
      </ol>
      <figcaption className="mt-1.5 text-meta text-muted">辿り方（公式ページの表示の言葉。サイソクが作った図です）</figcaption>
    </figure>
  );
}

export function OfficialDesk({ items, heading }: { items: DeskEntry[]; heading?: string }) {
  return (
    <section aria-labelledby="official-desk-heading" id="official-desk" className="dbx dbx-desk mt-12 max-w-[40em]">
      <BoxHeading id="official-desk-heading" kicker="公式窓口" heading={heading} fallback="公式窓口" />
      <p className="mt-1.5 text-note text-muted">SMSやメールに書かれた連絡先ではなく、ここにある公式の窓口を使ってください。</p>
      <div className="mt-4 grid gap-3">
        {items.map((desk, index) => (
          <div key={index} className="rounded-2xl border border-line-strong p-5">
            <p className="text-desc font-bold leading-snug text-ink">{desk.name}</p>
            {(desk.phone || desk.hours) && (
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-note">
                {desk.phone && (
                  <>
                    <dt className="text-muted">電話</dt>
                    <dd>
                      <a href={`tel:${desk.phone.replace(/[^\d+]/g, "")}`} className="font-bold text-ink underline underline-offset-4">
                        {desk.phone}
                      </a>
                    </dd>
                  </>
                )}
                {desk.hours && (
                  <>
                    <dt className="text-muted">受付</dt>
                    <dd className="text-ink">{desk.hours}</dd>
                  </>
                )}
              </dl>
            )}
            {desk.note && <p className="mt-2 text-note leading-[1.75] text-ink-soft">{desk.note}</p>}
            {desk.howTo && desk.howTo.length >= 2 && <RouteFigure steps={desk.howTo} label={desk.name} />}
            <a
              href={desk.url}
              target="_blank"
              rel="noopener"
              className="mt-3.5 flex min-h-11 items-center justify-between gap-3 rounded-xl bg-ink px-4 py-2.5 text-note font-bold text-paper hover:opacity-90"
            >
              <span className="min-w-0 truncate">公式ページを開く（{sourceLabel(desk.url)}）</span>
              <span aria-hidden>→</span>
            </a>
          </div>
        ))}
      </div>
    </section>
  );
}

/** 判断ガイド（問いごとに、状況 → おすすめ → 理由 → 出どころ。スマホでは1行を縦に積んだカード） */
export function DecisionGuide({ groups, heading }: { groups: { question: string; rows: GuideRow[] }[]; heading?: string }) {
  return (
    <section aria-labelledby="decision-guide-heading" id="decision-guide" className="dbx dbx-guide mt-12 max-w-[40em]">
      <BoxHeading id="decision-guide-heading" kicker="判断ガイド" heading={heading} fallback="迷ったときの判断ガイド" />
      <p className="mt-1.5 text-note text-muted">状況ごとのおすすめと理由です。どれを選ぶかは、ご自身の状況で決めてください。</p>
      <div className="mt-4 grid gap-5">
        {groups.map((group, gi) => (
          <div key={gi}>
            <h3 className="text-desc font-bold text-ink">{group.question}</h3>
            <div className="mt-2 grid gap-2.5">
              {group.rows.map((row, ri) => (
                <dl key={ri} className="grid gap-x-3 gap-y-1.5 rounded-2xl border border-line p-4 text-note sm:grid-cols-[5.5em_1fr]">
                  <dt className="font-bold text-muted">状況</dt>
                  <dd className="text-ink">{row.situation}</dd>
                  <dt className="font-bold text-muted">おすすめ</dt>
                  <dd className="font-bold text-ink">{row.recommend}</dd>
                  <dt className="font-bold text-muted">理由</dt>
                  <dd className="leading-[1.75] text-ink-soft">{row.reason}</dd>
                  <dt className="font-bold text-muted">出どころ</dt>
                  <dd>
                    <SourceLink url={row.source} general={row.general} />
                  </dd>
                </dl>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
