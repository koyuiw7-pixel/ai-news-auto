import { COMPARE_PUBLIC } from "@/lib/buying-guides";
import type { Metadata } from "next";
import Link from "next/link";
import { formatDate } from "@/lib/articles";
import { getAllBuyingGuides, resolveProducts } from "@/lib/buying-guides";

export const metadata: Metadata = {
  title: "比較ガイド：AI時代の道具を公式情報で比べる",
  description:
    "セキュリティソフト、Dify・n8n用のVPS、AIボイスレコーダー、ローカルLLM用PC、動画編集ソフト、AI英会話などを、公式情報と価格をもとに比較。選び方とよくある質問もまとめています。",
  alternates: { canonical: "/compare" },
  ...(COMPARE_PUBLIC ? {} : { robots: { index: false, follow: true } }),
};

/** 比較ガイドの一覧 */
export default function CompareIndexPage() {
  const guides = getAllBuyingGuides();
  return (
    <div className="mx-auto max-w-[920px] px-5 py-10 sm:px-8 sm:py-14">
      <p className="eyebrow">COMPARE</p>
      <h1 className="display mt-2 text-[1.9rem] sm:text-[2.4rem]">比較ガイド</h1>
      <p className="mt-3 max-w-[60ch] text-[14.5px] leading-[1.9] text-ink-soft">
        AIを使うための道具やサービスを、各社の公式情報と価格をもとに比べました。価格は定期的に確認し直しています。
      </p>
      <p className="mt-3 inline-block rounded-full bg-surface px-2 py-0.5 text-[10.5px] font-bold text-muted">
        本ページはプロモーションを含みます
      </p>
      <ul className="mt-10 grid gap-3 sm:grid-cols-2">
        {guides.map((guide) => {
          const names = resolveProducts(guide).map((p) => p.item.name);
          return (
            <li key={guide.slug}>
              <Link
                href={`/compare/${guide.slug}`}
                className="group flex h-full flex-col gap-2.5 rounded-2xl border border-line p-5 transition-colors hover:border-ink"
              >
                <span className="index-num text-[11.5px] text-muted">{formatDate(guide.updatedAt)} 更新・{names.length}件を比較</span>
                <span className="text-[17px] font-bold leading-snug text-ink group-hover:underline">{guide.title}</span>
                <span className="line-clamp-2 text-[13px] leading-[1.7] text-ink-soft">{names.join(" / ")}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
