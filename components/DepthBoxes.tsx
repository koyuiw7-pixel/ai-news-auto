/**
 * 記事を一歩深くする欄（2026-11-09 オーナー指摘・台帳 A66）。中身は scripts/depth_fields.py が公式ページから作る。
 * どの項目も読んだ公式ページの URL（source）を持ち、数字・「」の名前・URL はそのページにあるものだけ（プログラムで照合済み）。
 *   InsightBox     「なるほど」: 誰でも知っている注意ではなく、公式ページにだけある具体的な事実（記事の上のほう）
 *   CauseBox       「なぜ起きた？」: 公式ページが書く原因・背景。未発表なら「調査中」とはっきり書く
 *   WorriesBlock   「こんな不安ありませんか」: 読者の不安への答えと行動（一般の注意のページが出典のものは札を付ける）
 *   ActionSteps    「すぐにできること」の手順つき版（todayActions の代わりに出す）
 *   OfficialDesk   「公式窓口」: 正式名・電話・受付時間・押せる URL と、そのページへの辿り方の図（画面の写真は使わない。自前の図）
 */
import type { Cause, DeskEntry, InsightItem, StepItem, WorryItem } from "@/lib/depth";
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

export function InsightBox({ items }: { items: InsightItem[] }) {
  return (
    <section aria-labelledby="insight-heading" className="mb-8 max-w-[40em] rounded-2xl border-2 border-accent bg-accent-soft p-5 sm:p-6">
      <h2 id="insight-heading" className="flex items-center gap-2 text-desc font-bold text-ink">
        <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-accent text-meta font-bold text-accent-ink">
          !
        </span>
        なるほどポイント
      </h2>
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

export function CauseBox({ cause }: { cause: Cause }) {
  return (
    <section aria-labelledby="cause-heading" className="mt-12 max-w-[40em] rounded-2xl bg-surface p-5 sm:p-6">
      <h2 id="cause-heading" className="flex flex-wrap items-center gap-2 t-h3">
        {cause.status === "background" ? "なぜ変わる？" : "なぜ起きた？"}
        {cause.status === "investigating" && (
          <span className="rounded-sm border border-line-strong px-2 py-[1px] text-badge font-bold text-ink-soft">原因は調査中</span>
        )}
      </h2>
      <p className="mt-3 text-desc leading-[1.85] text-ink">{cause.text}</p>
      <SourceLink url={cause.source} />
    </section>
  );
}

export function WorriesBlock({ items }: { items: WorryItem[] }) {
  return (
    <section aria-labelledby="worries-heading" className="mt-12 max-w-[40em]">
      <h2 id="worries-heading" className="t-h2">
        こんな不安ありませんか
      </h2>
      <div className="mt-4 grid gap-3">
        {items.map((item, index) => (
          <details key={index} className="group rounded-2xl border border-line px-5 py-4 open:border-line-strong" open={index < 2}>
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
      </div>
    </section>
  );
}

export function ActionSteps({ items }: { items: StepItem[] }) {
  return (
    <section aria-labelledby="today-actions-heading" className="mt-12 max-w-[40em] rounded-2xl border border-line-strong p-5 sm:p-6">
      <h2 id="today-actions-heading" className="t-h3">
        すぐにできること
      </h2>
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

export function OfficialDesk({ items }: { items: DeskEntry[] }) {
  return (
    <section aria-labelledby="official-desk-heading" className="mt-12 max-w-[40em]">
      <h2 id="official-desk-heading" className="t-h2">
        公式窓口
      </h2>
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
