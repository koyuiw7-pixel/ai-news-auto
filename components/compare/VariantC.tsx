import Diagnosis, { type DiagnosisProduct } from "./Diagnosis";
import {
  Breadcrumb,
  CompareTable,
  Disclosure,
  FaqList,
  GuideMeta,
  HowWeMade,
  OutLink,
  PrMark,
  PriceLine,
  ProductVisual,
  RelatedNews,
  SourceList,
  VerdictMark,
} from "./parts";
import type { GuideView } from "./view";

/**
 * C：診断チャート型。最初に3つの質問（用途・予算・端末）で候補を絞り、そのあと表で確かめる。
 */
export default function VariantC({ view }: { view: GuideView }) {
  const { guide, products, personas } = view;
  const diagnosisProducts: DiagnosisProduct[] = products.map((p) => ({
    key: p.key,
    name: p.item.name,
    maker: p.maker,
    category: p.category,
    image: p.item.image,
    price: p.price || "公式サイトで確認",
    priceNote: p.priceNote,
    bestFor: p.bestFor,
    sponsored: p.sponsored,
    url: p.item.url,
    fit: p.fit ?? {},
  }));

  return (
    <div className="relative mx-auto max-w-[1000px] px-4 py-6 sm:px-8 sm:py-10">
      <GuideMeta view={view} />
      <Breadcrumb />

      <header className="mt-5">
        <p className="text-[12px] font-bold text-accent">比較ガイド ／ {products.length}件 ／ {view.checkedLabel}</p>
        <h1 className="display headline mt-2 text-[1.65rem] leading-[1.4] text-ink sm:text-[2.3rem]">{guide.title}</h1>
        <Disclosure view={view} className="mt-3" />
      </header>

      {/* 診断 */}
      <section aria-labelledby="c-quiz" className="mt-6 rounded-2xl border-2 border-ink p-4 sm:p-7">
        <h2 id="c-quiz" className="display text-[1.3rem] leading-tight text-ink sm:text-[1.6rem]">3つの質問で、候補を1つに絞る</h2>
        <p className="mt-1.5 text-[13px] leading-[1.8] text-ink-soft">
          用途・予算・端末を選ぶと、公式サイトの記載で条件に当てはまるものを上に出します。答えはこの画面の中だけで計算し、送信しません。
        </p>
        <div className="mt-5">
          <Diagnosis quiz={guide.quiz ?? []} products={diagnosisProducts} />
        </div>
      </section>

      {/* 結論ファースト（質問に答えない人向け） */}
      <section aria-labelledby="c-pick" className="mt-10">
        <SectionTitle id="c-pick" title="質問に答えずに選ぶなら" />
        <ul className="grid gap-px overflow-hidden rounded-xl border border-line bg-line">
          {personas.map((persona) => (
            <li key={persona.who} className="grid gap-2 bg-paper p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-6">
              <div>
                <p className="text-[14.5px] font-bold text-ink">{persona.who}は</p>
                <p className="mt-0.5 text-[12.5px] leading-[1.7] text-muted">{persona.why}</p>
              </div>
              <p className="flex flex-wrap gap-2">
                {persona.products.map((product) => (
                  <a
                    key={product.key}
                    href={`#p-${product.key}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-ink px-2.5 py-1.5 text-[14px] font-black text-ink hover:bg-ink hover:text-paper"
                  >
                    {product.item.name}
                    {product.sponsored && <PrMark className="opacity-70" />}
                    <span aria-hidden>→</span>
                  </a>
                ))}
              </p>
            </li>
          ))}
        </ul>
      </section>

      {/* サイソク判定（表の上に要約） */}
      <section aria-labelledby="c-verdict" className="mt-10">
        <SectionTitle id="c-verdict" title="サイソク判定" note="公式の記載を4項目に整理。点数はつけていません" />
        <div className="relative -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <table className="w-full min-w-[640px] border-collapse text-left text-[12.5px]">
            <thead>
              <tr className="border-b-2 border-ink text-[11.5px] text-ink">
                <th scope="col" className="sticky left-0 z-10 bg-paper py-2 pr-3 font-bold">製品</th>
                <th scope="col" className="px-3 py-2 font-bold">日本で使える</th>
                <th scope="col" className="px-3 py-2 font-bold">無料で試せる</th>
                <th scope="col" className="px-3 py-2 font-bold">料金の目安</th>
                <th scope="col" className="px-3 py-2 font-bold">向いている人</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) =>
                product.verdict ? (
                  <tr key={product.key} data-col={product.key} className="border-b border-line align-top">
                    <th scope="row" className="sticky left-0 z-10 bg-paper py-2.5 pr-3 text-[13px] font-black text-ink">
                      {product.item.name}
                      {product.sponsored && <PrMark className="ml-1.5 align-[1px] text-muted" />}
                    </th>
                    <td className="px-3 py-2.5 text-ink-soft">
                      <VerdictMark level={product.verdict.japan.level} className="mr-1" />
                      {product.verdict.japan.text}
                    </td>
                    <td className="px-3 py-2.5 text-ink-soft">
                      <VerdictMark level={product.verdict.freeTrial.level} className="mr-1" />
                      {product.verdict.freeTrial.text}
                    </td>
                    <td className="px-3 py-2.5 font-bold tabular-nums text-ink">{product.verdict.cost}</td>
                    <td className="px-3 py-2.5 text-ink-soft">{product.verdict.bestFor}</td>
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="c-table" className="mt-10">
        <SectionTitle id="c-table" title="詳しい比較表" note="診断でいちばん当てはまった列は色が付きます" />
        <CompareTable view={view} tone="plain" />
      </section>

      {/* 選び方：フローチャート風の縦の流れ */}
      <section aria-labelledby="c-how" className="mt-12">
        <SectionTitle id="c-how" title="選び方の順番" />
        <ol className="relative grid gap-0">
          {(guide.decisionPoints ?? []).map((point, index, all) => (
            <li key={point.title} className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3">
              <div className="flex flex-col items-center">
                <span className="index-num grid size-9 shrink-0 place-items-center rounded-full bg-ink text-[13px] font-semibold text-paper">
                  {index + 1}
                </span>
                {index < all.length - 1 && <span aria-hidden className="w-0.5 flex-1 bg-line-strong" />}
              </div>
              <div className="pb-6 pt-1.5">
                <h3 className="text-[16px] font-black leading-snug text-ink">{point.title}</h3>
                <p className="mt-1 text-[14px] leading-[1.85] text-ink-soft">{point.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="c-products" className="mt-8">
        <SectionTitle id="c-products" title="1つずつ：できること・注意点" />
        <div className="grid gap-4">
          {products.map((product) => (
            <details key={product.key} id={`p-${product.key}`} className="group scroll-mt-24 rounded-xl border border-line open:border-ink" open>
              <summary className="flex cursor-pointer list-none items-center gap-4 p-4">
                <ProductVisual product={product} compact className="size-14 shrink-0 rounded-lg" />
                <span className="min-w-0 flex-1">
                  <span className="block text-[11px] font-bold text-muted">{product.category}</span>
                  <span className="flex flex-wrap items-center gap-2 text-[18px] font-black leading-snug text-ink">
                    {product.item.name}
                    {product.sponsored && <PrMark className="text-muted" />}
                  </span>
                  <span className="index-num block text-[13px] font-semibold text-ink">{product.price || "公式サイトで確認"}</span>
                </span>
                <span aria-hidden className="text-muted transition-transform group-open:rotate-180 motion-reduce:transition-none">⌄</span>
              </summary>
              <div className="border-t border-line p-4 pt-3">
                <PriceLine product={product} label={view.checkedLabel} />
                <p className="mt-2 text-[14.5px] leading-[1.9] text-ink-soft">{product.summary}</p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <h4 className="text-[13px] font-black text-go">できること</h4>
                    <ul className="mt-1.5 grid gap-1.5 text-[13.5px] leading-[1.75] text-ink-soft">
                      {product.strengths.map((text) => (
                        <li key={text} className="grid grid-cols-[1rem_1fr] gap-1"><span aria-hidden className="text-go">○</span>{text}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="text-[13px] font-black text-ink">注意点</h4>
                    <ul className="mt-1.5 grid gap-1.5 text-[13.5px] leading-[1.75] text-ink-soft">
                      {product.limits.map((text) => (
                        <li key={text} className="grid grid-cols-[1rem_1fr] gap-1"><span aria-hidden className="text-muted">△</span>{text}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <SourceList product={product} />
                  <OutLink
                    product={product}
                    className="flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-accent px-5 text-[13.5px] font-bold text-white hover:opacity-90"
                  >
                    公式サイトで見る <span aria-hidden>↗</span>
                  </OutLink>
                </div>
              </div>
            </details>
          ))}
        </div>
      </section>

      {view.related.length > 0 && (
        <section aria-labelledby="c-news" className="mt-12">
          <SectionTitle id="c-news" title="最新ニュース" note="サイソクが報じた音声AI・文字起こしの関連記事" />
          <RelatedNews view={view} />
        </section>
      )}

      <section aria-labelledby="c-faq" className="mt-12">
        <SectionTitle id="c-faq" title="よくある質問" />
        <FaqList view={view} />
      </section>

      <section aria-labelledby="c-made" className="mt-10 rounded-xl bg-surface p-5">
        <h2 id="c-made" className="text-[14px] font-black text-ink">このガイドの作り方</h2>
        <HowWeMade view={view} className="mt-2" />
      </section>
    </div>
  );
}

function SectionTitle({ id, title, note }: { id: string; title: string; note?: string }) {
  return (
    <div className="mb-4 border-b border-ink pb-2">
      <h2 id={id} className="display text-[1.25rem] leading-tight text-ink sm:text-[1.45rem]">{title}</h2>
      {note && <p className="mt-0.5 text-[11.5px] text-muted">{note}</p>}
    </div>
  );
}
