import type { Metadata } from "next";
import { withPageShare } from "@/lib/page-share";
import Link from "next/link";
import { formatDate } from "@/lib/articles";
import { getAllBuyingGuides, getIndexableBuyingGuides, guideShortName, isGuideIndexable, resolveProducts } from "@/lib/buying-guides";
import { PrMark, ProductVisual } from "@/components/compare/parts";

// 2026-11-11 オーナー承認（台帳 W42）: 暮らしとお金の比較ページを検索に出す。一覧も検索に出し、検索に出すページを先に並べる
export const metadata: Metadata = withPageShare("compare", "/compare", {
  title: "比較ガイド：格安SIM・光回線・電気料金・ふるさと納税を公式の料金で比べる",
  description:
    "格安SIM 16社、光回線 15社、電気料金 14プラン、ふるさと納税サイト、保険相談の窓口などを、各社の公式サイトの料金と条件だけで比較。使い方に合わせて絞り込めます。",
  alternates: { canonical: "/compare" },
  ...(getIndexableBuyingGuides().length > 0 ? {} : { robots: { index: false, follow: true } }),
});

/** 比較ガイドの一覧 */
export default function CompareIndexPage() {
  // 検索に出す（作り直した）ページを先に、旧形式のページは後ろ
  const guides = [...getAllBuyingGuides()].sort((a, b) => Number(isGuideIndexable(b)) - Number(isGuideIndexable(a)));
  return (
    <div className="mx-auto max-w-[920px] px-5 py-10 sm:px-8 sm:py-14">
      <p className="eyebrow">COMPARE</p>
      <h1 className="t-h1 mt-2">比較ガイド</h1>
      <p className="t-lead mt-3">
        AIを使うための道具やサービスを、各社の公式情報と価格をもとに比べました。価格は定期的に確認し直しています。
      </p>
      {/* 2026-11-11 オーナー決定（台帳 W40）「広告の表示は『PR』だけ。全部で」: ページ冒頭の「本ページはプロモーションを含みます」は出さない。広告の枠ごとの「PR」の札で示す */}
      <ul className="mt-10 grid gap-4 sm:grid-cols-2">
        {guides.map((guide) => {
          const products = resolveProducts(guide);
          const shown = products.slice(0, 4);
          const rest = products.length - shown.length;
          const hasPr = products.some((p) => p.sponsored);
          return (
            <li key={guide.slug}>
              <Link
                href={`/compare/${guide.slug}`}
                className="group flex h-full flex-col overflow-hidden rounded-2xl border border-line transition-colors hover:border-ink"
              >
                {/* 比べている商品の写真（提携外のサービスは名前の札） */}
                <span className="grid grid-cols-4 gap-px border-b border-line bg-line" aria-hidden>
                  {shown.map((product) => (
                    <ProductVisual key={product.key} product={product} compact className="aspect-square w-full border-0" />
                  ))}
                  {Array.from({ length: 4 - shown.length }, (_, i) => (
                    <span key={`blank-${i}`} className="aspect-square bg-surface" />
                  ))}
                </span>
                <span className="flex flex-1 flex-col gap-2 p-4">
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-muted">
                    <span className="index-num font-semibold text-ink">{products.length}件を比較</span>
                    <span aria-hidden>・</span>
                    <span className="index-num">{formatDate(guide.updatedAt)} 更新</span>
                    {hasPr && <PrMark className="ml-auto" />}
                  </span>
                  <span className="text-[16.5px] font-bold leading-snug text-ink group-hover:underline">{guideShortName(guide)}</span>
                  <span className="line-clamp-2 text-desc leading-[1.7] text-ink-soft">
                    {products.map((p) => p.item.name).join(" / ")}
                    {rest > 0 && ` ほか`}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
