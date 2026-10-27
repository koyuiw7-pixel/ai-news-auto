import Link from "next/link";
import ArticleCard from "@/components/ArticleCard";
import { Pixels } from "@/components/rail/parts";
import type { ResolvedProduct, VerdictLevel } from "@/lib/buying-guides";
import { formatDate } from "@/lib/articles";
import type { GuideView } from "./view";

/** 構造化データと計測ピクセル（どのデザインでも同じ） */
export function GuideMeta({ view }: { view: GuideView }) {
  return (
    <>
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(view.jsonLd) }}
      />
      <Pixels pixels={view.pixels} />
    </>
  );
}

export function Breadcrumb() {
  return (
    <nav aria-label="パンくず" className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
      <Link href="/" className="hover:text-accent">ホーム</Link>
      <span aria-hidden>/</span>
      <Link href="/compare" className="hover:text-accent">比較ガイド</Link>
    </nav>
  );
}

/** 広告（提携商品）の印。四角い枠の「PR」だけにして目立たせすぎない */
export function PrMark({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-grid h-[18px] place-items-center rounded-[3px] border border-current px-1 text-[10px] font-bold leading-none tracking-wider ${className}`}
      title="提携先の商品（リンク経由の購入で紹介料が入ることがあります）"
    >
      PR
    </span>
  );
}

/** 公式サイトへのリンク。提携商品は sponsored、提携していない商品は nofollow */
export function OutLink({
  product,
  className = "",
  children,
}: {
  product: ResolvedProduct;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={product.item.url}
      target="_blank"
      rel={product.sponsored ? "sponsored noopener noreferrer" : "nofollow noopener"}
      className={className}
    >
      {children}
      <span className="sr-only">（{product.sponsored ? "PR・" : ""}新しいタブで開きます）</span>
    </a>
  );
}

/**
 * 商品の見た目。提携商品は offers.json の公式商品画像、
 * 提携していない商品は画像を勝手に使わず、名前と種別だけの無地の札にする。
 */
export function ProductVisual({
  product,
  className = "",
  eager = false,
  compact = false,
}: {
  product: ResolvedProduct;
  className?: string;
  eager?: boolean;
  compact?: boolean;
}) {
  if (product.item.image) {
    return (
      <span className={`relative grid place-items-center overflow-hidden bg-white ${className}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={product.item.image}
          alt={product.item.name}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          className={`size-full object-contain ${compact ? "p-1.5" : "p-4"}`}
        />
      </span>
    );
  }
  if (compact) {
    // 小さい札では長い名前が切れるので、メーカー名だけを大きく見せる
    return (
      <span
        role="img"
        aria-label={`${product.item.name}（${product.category ?? "サービス"}）`}
        className={`@container grid place-items-center overflow-hidden border border-line bg-surface text-center ${className}`}
      >
        <span className="flex flex-col items-center gap-1 px-1">
          <span className="text-[10px] font-black leading-none text-ink @[72px]:text-[12px]">{product.maker ?? product.item.name}</span>
          <span className="hidden text-[9.5px] font-bold leading-tight text-muted @[72px]:block">{product.category}</span>
        </span>
      </span>
    );
  }
  return (
    <span
      role="img"
      aria-label={`${product.item.name}（${product.category ?? "サービス"}）`}
      className={`relative flex flex-col justify-between overflow-hidden border border-line bg-surface p-3.5 text-left ${className}`}
    >
      <span className="index-num text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{product.maker}</span>
      <span className="text-[17px] font-black leading-tight text-ink">{product.item.name}</span>
      <span className="text-[11px] font-bold text-ink-soft">{product.category}</span>
    </span>
  );
}

const VERDICT_MARK: Record<VerdictLevel, { glyph: string; label: string; className: string }> = {
  yes: { glyph: "○", label: "対応", className: "text-go" },
  partial: { glyph: "△", label: "条件つき", className: "text-ink-soft" },
  no: { glyph: "×", label: "非対応", className: "text-live" },
};

/** ○△× の判定。記号だけに頼らず、読み上げ用の言葉も付ける */
export function VerdictMark({ level, className = "" }: { level: VerdictLevel; className?: string }) {
  const mark = VERDICT_MARK[level];
  return (
    <span className={`font-black ${mark.className} ${className}`}>
      <span aria-hidden>{mark.glyph}</span>
      <span className="sr-only">{mark.label}</span>
    </span>
  );
}

/**
 * 比較表。商品を列、比べる項目を行にし、1列目（項目名）をスクロール中も固定する。
 * tone で見た目だけ変える（A=報道の表、B=店頭POP、C=診断で選ばれた列を強調）。
 */
export function CompareTable({
  view,
  tone,
  withImages = false,
}: {
  view: GuideView;
  tone: "news" | "pop" | "plain";
  withImages?: boolean;
}) {
  const { products, rows } = view;
  const head =
    tone === "news"
      ? "bg-ink text-paper"
      : tone === "pop"
        ? "bg-paper text-ink border-b-2 border-ink"
        : "bg-surface text-ink border-b border-line-strong";
  const stickyBg = tone === "news" ? "bg-ink" : tone === "pop" ? "bg-paper" : "bg-surface";
  return (
    <div className="-mx-4 sm:mx-0">
      <div
        className="relative overflow-x-auto overscroll-x-contain border-y border-line sm:rounded-xl sm:border"
        role="region"
        aria-label="比較表（横にスクロールできます）"
        tabIndex={0}
      >
        <table className="w-full min-w-[980px] border-collapse text-left text-[12.5px] leading-[1.65]">
          <caption className="sr-only">{view.guide.shortName ?? view.guide.title}の比較表（{view.checkedLabel}）</caption>
          <thead>
            <tr className={head}>
              <th scope="col" className={`sticky left-0 z-20 w-[112px] min-w-[112px] px-3 py-3 text-[11px] font-bold ${stickyBg}`}>
                項目
              </th>
              {products.map((product) => (
                <th
                  key={product.key}
                  scope="col"
                  data-col={product.key}
                  className="min-w-[150px] px-3 py-3 align-bottom font-bold"
                >
                  {withImages && (
                    <ProductVisual product={product} compact className="mb-2 h-20 w-full rounded-md" />
                  )}
                  <span className="flex items-start gap-1.5">
                    <a href={`#p-${product.key}`} className="text-[13px] leading-snug hover:underline">
                      {product.item.name}
                    </a>
                    {product.sponsored && <PrMark className="mt-0.5 shrink-0 opacity-80" />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.key} className={`border-b border-line align-top ${index % 2 === 1 && tone !== "pop" ? "bg-surface/50" : ""}`}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 w-[112px] min-w-[112px] border-r border-line bg-paper px-3 py-3 text-[11.5px] font-bold leading-snug text-ink"
                >
                  {row.label}
                </th>
                {products.map((product) => {
                  const value = product.cells?.[row.key] ?? "公式サイトで確認";
                  const unknown = value === "公式サイトで確認";
                  return (
                    <td
                      key={product.key}
                      data-col={product.key}
                      className={`px-3 py-3 ${row.key === "price" ? "text-[13px] font-black tabular-nums text-ink" : unknown ? "text-muted" : "text-ink-soft"}`}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="align-top">
              <th scope="row" className="sticky left-0 z-10 border-r border-line bg-paper px-3 py-3 text-[11.5px] font-bold text-ink">
                公式サイト
              </th>
              {products.map((product) => (
                <td key={product.key} data-col={product.key} className="px-3 py-3">
                  <OutLink
                    product={product}
                    className="inline-flex h-9 items-center gap-1 whitespace-nowrap rounded-md border border-ink px-3 text-[12px] font-bold text-ink hover:bg-ink hover:text-paper"
                  >
                    公式 <span aria-hidden>↗</span>
                  </OutLink>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-2 px-4 text-[11px] text-muted sm:px-0">
        {view.checkedLabel}。「公式サイトで確認」は公式ページに記載が見つからなかった項目です。スマホでは表を横にスクロールできます。
      </p>
    </div>
  );
}

/** 商品ごとの出典リンク */
export function SourceList({ product }: { product: ResolvedProduct }) {
  if (!product.sources?.length) return null;
  return (
    <p className="text-[11px] leading-relaxed text-muted">
      出典：
      {product.sources.map((source, index) => (
        <span key={source.url}>
          {index > 0 && "／"}
          <a href={source.url} target="_blank" rel="nofollow noopener" className="underline underline-offset-2 hover:text-accent">
            {source.label}
          </a>
        </span>
      ))}
    </p>
  );
}

/** 価格の時点と出典の一行 */
export function PriceLine({ product, label }: { product: ResolvedProduct; label: string }) {
  return (
    <span className="text-[11px] text-muted">
      {product.priceNote ? `${product.priceNote}・` : ""}
      {product.priceSource ? label : "公式サイトで確認"}
    </span>
  );
}

export function FaqList({ view, headingClass = "" }: { view: GuideView; headingClass?: string }) {
  return (
    <div className="divide-y divide-line border-y border-line">
      {view.guide.faq.map((item) => (
        <details key={item.q} className="group py-4">
          <summary className={`flex cursor-pointer list-none items-start justify-between gap-4 text-[15px] font-bold text-ink ${headingClass}`}>
            <span>Q. {item.q}</span>
            <span aria-hidden className="mt-0.5 text-muted transition-transform group-open:rotate-45 motion-reduce:transition-none">＋</span>
          </summary>
          <p className="mt-3 text-[14.5px] leading-[1.9] text-ink-soft">A. {item.a}</p>
        </details>
      ))}
    </div>
  );
}

export function RelatedNews({ view }: { view: GuideView }) {
  if (view.related.length === 0) return null;
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {view.related.map((article) => (
        <ArticleCard key={article.slug} article={article} />
      ))}
    </div>
  );
}

/** このガイドの作り方（広告の明示・編集方針へのリンク） */
export function HowWeMade({ view, className = "" }: { view: GuideView; className?: string }) {
  return (
    <div className={`text-[12.5px] leading-[1.85] text-ink-soft ${className}`}>
      <p>{view.guide.howWeMade}</p>
      <p className="mt-2">
        価格・仕様・キャンペーンは変わることがあります。申し込み前に各公式サイトで最新情報をご確認ください。
        制作方法は<Link href="/editorial-policy" className="mx-1 text-accent underline underline-offset-2">編集方針</Link>、
        誤りのご指摘は<Link href="/contact" className="mx-1 text-accent underline underline-offset-2">お問い合わせ</Link>へ。
      </p>
      <p className="index-num mt-2 text-[11px] text-muted">
        公開 {formatDate(view.guide.publishedAt)} ／ 最終更新 <time dateTime={view.guide.updatedAt}>{formatDate(view.guide.updatedAt)}</time>
      </p>
    </div>
  );
}

/** 冒頭の一行の広告表記 */
export function Disclosure({ view, className = "" }: { view: GuideView; className?: string }) {
  return (
    <p className={`text-[12px] leading-[1.75] text-muted ${className}`}>
      {view.hasSponsored && (
        <>
          <PrMark className="mr-1.5 align-[1px] text-ink" />
          本ページはプロモーションを含みます。「PR」の付いた商品は提携先で、リンク経由の購入で当サイトに紹介料が入ることがあります。それ以外は提携していません。
        </>
      )}
      編集部が実際に使って評価したものではありません。
    </p>
  );
}
