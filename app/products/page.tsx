import type { Metadata } from "next";
import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import { formatDate } from "@/lib/articles";
import { COMPANIES, getCompany } from "@/lib/companies";
import { getAllProducts, type Product } from "@/lib/products";

export const metadata: Metadata = {
  title: "製品まとめ：AIモデル・アプリの料金と日本で使えるか",
  description:
    "GPT-6.1 Terra、Claude Opus 5.5、Gemini 4 Argonなど、記事に出てきたAIモデル・アプリ・ガジェットを製品ごとに1ページで整理。料金・日本で使えるか・これまでの流れを、記事が増えるたびに更新します。",
  alternates: { canonical: "/products" },
};

/** 製品まとめの一覧（企業ごと） */
export default function ProductsPage() {
  const products = getAllProducts();
  // lib/companies.ts の並び（記事の多い企業から）→ その他の企業は名前順
  const known = COMPANIES.map((c) => c.slug);
  const groups = new Map<string, Product[]>();
  for (const product of products) {
    const key = product.company === "other" ? `other:${product.companyName}` : product.company;
    groups.set(key, [...(groups.get(key) ?? []), product]);
  }
  const keys = [...groups.keys()].sort((a, b) => {
    const ia = known.indexOf(a);
    const ib = known.indexOf(b);
    if (ia >= 0 && ib >= 0) return groups.get(b)!.length - groups.get(a)!.length || ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return a.localeCompare(b);
  });

  return (
    <div className="mx-auto max-w-[860px] px-4 py-10 sm:px-8 sm:py-14">
      <h1 className="display text-[1.9rem] sm:text-[2.4rem]">製品まとめ</h1>
      <p className="mt-3 max-w-[60ch] text-[15px] leading-[1.95] text-ink-soft">
        記事に出てきたAIモデル・アプリ・ガジェットを、製品ごとに1ページにまとめています。
        料金や日本で使えるかは、新しい記事が出るたびに更新します。
      </p>

      <div className="mt-10 grid gap-12">
        {keys.map((key) => {
          const items = groups.get(key)!;
          const company = items[0].company === "other" ? undefined : getCompany(items[0].company);
          return (
            <section key={key} aria-label={items[0].companyName}>
              <h2 className="flex items-center gap-2 border-b border-ink pb-2 text-[15px] font-bold text-ink">
                {company ? <CompanyMark company={company} size={20} withName /> : items[0].companyName}
                <span className="index-num ml-auto text-[11.5px] font-normal text-muted">{items.length}製品</span>
              </h2>
              <ul>
                {items.map((product) => (
                  <li key={product.slug} className="border-b border-line">
                    <Link href={`/products/${product.slug}`} className="group block py-4">
                      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="text-[16.5px] font-bold text-ink group-hover:underline">{product.name}</span>
                        <span className="text-[12px] text-muted">{product.category}</span>
                        <span className="index-num ml-auto text-[11.5px] text-muted">
                          記事{product.articles.length}本・{formatDate(product.updatedAt)}更新
                        </span>
                      </span>
                      <span className="mt-1.5 line-clamp-2 block text-[13.5px] leading-[1.8] text-ink-soft">
                        {product.overview.text}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
