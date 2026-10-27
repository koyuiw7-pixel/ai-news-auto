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
 * B：店頭POP比較表／雑誌型。商品を写真つきで横一列に並べ、結論は大きなカードで見せる。
 */
export default function VariantB({ view }: { view: GuideView }) {
  const { guide, products, personas } = view;
  return (
    <div className="relative mx-auto max-w-[1160px] px-4 py-6 sm:px-8 sm:py-10">
      <GuideMeta view={view} />
      <Breadcrumb />

      <header className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:items-end lg:gap-10">
        <div>
          <p className="index-num text-[11.5px] font-semibold text-accent">
            COMPARE ／ {products.length}製品 ／ {view.checkedLabel}
          </p>
          <h1 className="display headline mt-2 text-[1.75rem] leading-[1.35] text-ink sm:text-[2.6rem]">{guide.title}</h1>
        </div>
        <div>
          <p className="text-[14.5px] leading-[1.9] text-ink-soft">{guide.intro}</p>
          <Disclosure view={view} className="mt-2" />
        </div>
      </header>

      {/* 店頭の棚：写真つきで横一列 */}
      <section aria-label="比較する製品" className="mt-8">
        <ul className="relative -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-3 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 lg:grid-cols-6">
          {products.map((product, index) => (
            <li key={product.key} className="w-[44vw] max-w-[200px] shrink-0 snap-start sm:w-auto sm:max-w-none">
              <a
                href={`#p-${product.key}`}
                className="group flex h-full flex-col overflow-hidden rounded-xl border border-line bg-paper transition-colors hover:border-ink"
              >
                <ProductVisual product={product} eager={index < 3} className="aspect-square w-full" />
                <span className="flex flex-1 flex-col gap-1 border-t border-line p-3">
                  <span className="flex items-center justify-between gap-2 text-[10.5px] font-bold text-muted">
                    <span className="truncate">{product.category}</span>
                    {product.sponsored && <PrMark />}
                  </span>
                  <span className="text-[14.5px] font-black leading-snug text-ink group-hover:underline">{product.item.name}</span>
                  <span className="index-num mt-auto pt-1 text-[19px] font-semibold leading-none text-ink">
                    {product.price || "公式サイトで確認"}
                  </span>
                  <span className="text-[10.5px] leading-snug text-muted">{product.priceNote}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-muted">価格は{view.checkedLabel}。写真は提携先の公式商品画像、そのほかは名前のみ表示しています。</p>
      </section>

      {/* 結論カード */}
      <section aria-labelledby="b-pick" className="mt-12">
        <SectionTitle id="b-pick" kicker="結論" title="あなたに合うのはどれ？" />
        <ul className="grid gap-4 sm:grid-cols-2">
          {personas.map((persona) => (
            <li key={persona.who} className="flex flex-col rounded-2xl bg-surface p-5 sm:p-6">
              <p className="text-[13px] font-bold text-ink-soft">{persona.who}は</p>
              <div className="mt-3 flex flex-1 flex-col gap-3">
                {persona.products.map((product) => (
                  <div key={product.key} className="flex items-center gap-4">
                    <ProductVisual product={product} compact className="size-20 shrink-0 rounded-xl sm:size-24" />
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-[21px] font-black leading-tight text-ink sm:text-[24px]">
                        {product.item.name}
                      </p>
                      <p className="index-num mt-1 text-[13px] font-semibold text-ink">
                        {product.price || "公式サイトで確認"}
                        {product.sponsored && <PrMark className="ml-2 align-[1px] text-muted" />}
                      </p>
                    </div>
                  </div>
                ))}
                <p className="text-[13.5px] leading-[1.8] text-ink-soft">{persona.why}</p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {persona.products.map((product) => (
                  <OutLink
                    key={product.key}
                    product={product}
                    className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-xl bg-accent px-4 text-[13.5px] font-bold text-white hover:opacity-90"
                  >
                    {persona.products.length > 1 ? product.item.name : "公式サイトで見る"} <span aria-hidden>↗</span>
                  </OutLink>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* 比較表 */}
      <section aria-labelledby="b-table" className="mt-14">
        <SectionTitle id="b-table" kicker="比較表" title="9項目を横に並べて比べる" />
        <CompareTable view={view} tone="pop" withImages />
      </section>

      {/* 選び方 */}
      <section aria-labelledby="b-how" className="mt-14">
        <SectionTitle id="b-how" kicker="選び方" title="買う前の5つのチェック" />
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(guide.decisionPoints ?? []).map((point, index) => (
            <li key={point.title} className="rounded-2xl border border-line p-5">
              <p className="flex items-baseline gap-2">
                <span className="index-num text-[13px] font-semibold text-accent">CHECK {index + 1}</span>
              </p>
              <h3 className="mt-1.5 text-[16px] font-black leading-snug text-ink">{point.title}</h3>
              <p className="mt-2 text-[13.5px] leading-[1.85] text-ink-soft">{point.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* 商品ごと（雑誌の見開き風） */}
      <section aria-labelledby="b-products" className="mt-14">
        <SectionTitle id="b-products" kicker="製品ガイド" title="できること・注意点" />
        <div className="grid gap-6">
          {products.map((product) => (
            <article
              key={product.key}
              id={`p-${product.key}`}
              className="scroll-mt-24 overflow-hidden rounded-2xl border border-line lg:grid lg:grid-cols-[360px_minmax(0,1fr)]"
            >
              <div className="flex flex-col border-b border-line lg:border-b-0 lg:border-r">
                <ProductVisual product={product} className={`w-full lg:aspect-square ${product.item.image ? "aspect-[16/10]" : "aspect-[16/5]"}`} />
                {product.verdict && (
                  <dl className="grid grid-cols-2 border-t border-line text-[12px]">
                    <Cell label="日本で使える">
                      <VerdictMark level={product.verdict.japan.level} className="mr-1" />
                      {product.verdict.japan.text}
                    </Cell>
                    <Cell label="無料で試せる">
                      <VerdictMark level={product.verdict.freeTrial.level} className="mr-1" />
                      {product.verdict.freeTrial.text}
                    </Cell>
                    <Cell label="料金の目安">{product.verdict.cost}</Cell>
                    <Cell label="向いている人">{product.verdict.bestFor}</Cell>
                  </dl>
                )}
              </div>
              <div className="p-5 sm:p-7">
                <p className="flex items-center gap-2 text-[11.5px] font-bold text-muted">
                  {product.category}
                  {product.sponsored && <PrMark />}
                </p>
                <h3 className="mt-1 text-[24px] font-black leading-tight text-ink">{product.item.name}</h3>
                <p className="mt-2 flex flex-wrap items-baseline gap-x-2">
                  <span className="index-num text-[24px] font-semibold text-ink">{product.price || "公式サイトで確認"}</span>
                  <PriceLine product={product} label={view.checkedLabel} />
                </p>
                <p className="mt-3 text-[14.5px] leading-[1.9] text-ink-soft">{product.summary}</p>
                <div className="mt-5 grid gap-5 md:grid-cols-2">
                  <div>
                    <h4 className="border-b border-ink pb-1 text-[13px] font-black text-ink">できること</h4>
                    <ul className="mt-2 grid gap-1.5 text-[13.5px] leading-[1.75] text-ink-soft">
                      {product.strengths.map((text) => (
                        <li key={text} className="grid grid-cols-[1rem_1fr] gap-1"><span aria-hidden className="text-go">●</span>{text}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="border-b border-ink pb-1 text-[13px] font-black text-ink">注意点</h4>
                    <ul className="mt-2 grid gap-1.5 text-[13.5px] leading-[1.75] text-ink-soft">
                      {product.limits.map((text) => (
                        <li key={text} className="grid grid-cols-[1rem_1fr] gap-1"><span aria-hidden className="text-muted">●</span>{text}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="mt-5 grid gap-3">
                  <OutLink
                    product={product}
                    className="flex h-12 items-center justify-center gap-1.5 rounded-xl bg-accent text-[14px] font-bold text-white hover:opacity-90"
                  >
                    {product.item.name}の{product.sponsored ? "公式ストア" : "公式サイト"}へ <span aria-hidden>↗</span>
                  </OutLink>
                  <SourceList product={product} />
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {view.related.length > 0 && (
        <section aria-labelledby="b-news" className="mt-14">
          <SectionTitle id="b-news" kicker="ニュース" title="音声AIの最新ニュース" />
          <RelatedNews view={view} />
        </section>
      )}

      <section aria-labelledby="b-faq" className="mt-14 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:gap-10">
        <div>
          <SectionTitle id="b-faq" kicker="FAQ" title="よくある質問" />
          <FaqList view={view} />
        </div>
        <aside aria-labelledby="b-made" className="h-fit rounded-2xl bg-surface p-5">
          <h2 id="b-made" className="text-[14px] font-black text-ink">このガイドの作り方</h2>
          <HowWeMade view={view} className="mt-2" />
        </aside>
      </section>
    </div>
  );
}

function SectionTitle({ id, kicker, title }: { id: string; kicker: string; title: string }) {
  return (
    <div className="mb-5">
      <p className="text-[12px] font-bold text-accent">{kicker}</p>
      <h2 id={id} className="display text-[1.45rem] leading-tight text-ink sm:text-[1.85rem]">{title}</h2>
    </div>
  );
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-r border-line p-3 [&:nth-child(2n)]:border-r-0 [&:nth-last-child(-n+2)]:border-b-0">
      <dt className="text-[10.5px] font-bold text-muted">{label}</dt>
      <dd className="mt-0.5 font-bold leading-snug text-ink">{children}</dd>
    </div>
  );
}
