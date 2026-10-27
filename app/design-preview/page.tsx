import type { Metadata } from "next";
import DesignPreview from "@/components/design-preview/DesignPreview";
import type { PreviewData, PreviewModel } from "@/components/design-preview/data";
import { companyOf } from "@/lib/companies";
import { getAllArticles, sourceLabel, speedLabel } from "@/lib/articles";
import { getAllProducts } from "@/lib/products";
import { getPricing, priceRows } from "@/lib/pricing";

/**
 * ブランド配色3案の比較（オーナー確認用）。どこからもリンクせず、検索にも出さない。
 * 3案とも同じ実データ（料金表・最新記事・製品）を描く。採用案が決まったらルートごと消してよい。
 */
export const metadata: Metadata = {
  title: "配色デザイン案の比較（確認用）",
  robots: { index: false, follow: false, nocache: true },
};

/** 料金表と同じ計算の初期値（「ふつう」の使い方）での月額。並び順に使う */
const normalCost = (input: number, output: number) => (input * 439_000 + output * 139_000) / 1_000_000;

export default function DesignPreviewPage() {
  const pricing = getPricing();
  const rows = priceRows();

  // 日本で使える（条件付き含む）・料金が揃った現行モデルを安い順に6つ
  const models: PreviewModel[] = rows
    .filter((r) => r.kind === "api" && !r.legacy && r.input !== null && r.output !== null)
    .filter((r) => r.japan === "ok" || r.japan === "partial")
    .sort((a, b) => normalCost(a.input!, a.output!) - normalCost(b.input!, b.output!))
    .slice(0, 6)
    .map((r) => ({
      id: r.id,
      product: r.product,
      companyName: r.companyName,
      mark: r.mark,
      color: r.color,
      input: r.input!,
      output: r.output!,
      japan: r.japan,
      productSlug: r.productSlug,
    }));

  const articles = getAllArticles();
  const ai = articles.filter((a) => a.genreSlug === "ai");
  const latest = ai[0] ?? articles[0];
  const company = companyOf(latest);
  const roundup = ai.find((a) => a.type === "roundup");

  const products = getAllProducts();
  const product = products.find((p) => p.slug === models[0]?.productSlug) ?? products[0];
  const productPrice = rows.find((r) => r.kind === "api" && r.productSlug === product?.slug);

  const data: PreviewData = {
    models,
    updatedAt: pricing.updatedAt,
    modelCount: rows.filter((r) => r.kind === "api" && !r.legacy).length,
    articleCount: articles.length,
    article: {
      slug: latest.slug,
      title: latest.title,
      description: latest.description,
      publishedAt: latest.publishedAt,
      source: sourceLabel(latest),
      companyName: company.name,
      companyColor: company.color,
      speed: speedLabel(latest),
      cover: `/cover/${latest.slug}`,
    },
    roundupCount: roundup?.sourceCount ?? 0,
    product: product
      ? {
          slug: product.slug,
          name: product.name,
          category: product.category,
          companyName: product.companyName,
          mark: productPrice?.mark ?? product.companyName.slice(0, 1),
          color: productPrice?.color ?? "#555",
          overview: product.overview.text,
          articleCount: product.articles.length,
          updatedAt: product.updatedAt,
          input: productPrice?.input ?? null,
          output: productPrice?.output ?? null,
          japan: productPrice?.japan ?? "unknown",
        }
      : null,
  };

  return (
    <>
      {/* 各案が自前のヘッダーを持つので、サイト共通のヘッダー・フッターはこのページだけ隠す */}
      <style>{`body > header.site-header, body > footer { display: none !important; }`}</style>
      <DesignPreview data={data} />
    </>
  );
}
