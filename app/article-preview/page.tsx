import type { Metadata } from "next";
import Link from "next/link";
import type { Variant } from "@/components/article-preview/view";
import { PREVIEW_VARIANTS } from "./variants";

/** 記事ページのデザイン案の一覧（オーナー確認用。検索には出さない） */

export const metadata: Metadata = {
  title: "記事ページのデザイン案（確認用）",
  robots: { index: false, follow: false, nocache: true },
};

export default function ArticlePreviewIndex() {
  return (
    <div className="mx-auto max-w-[820px] px-5 py-10 sm:px-8">
      <p className="text-[12px] font-bold text-muted">確認用（検索には出ません）</p>
      <h1 className="display mt-2 text-[1.8rem] text-ink">記事ページのデザイン案</h1>
      <p className="mt-3 text-[15px] leading-[1.9] text-ink-soft">
        同じ記事（GPT-6.1 Terra）を3つのデザインで表示しています。どれも「文字の読みやすさ・要点・比較表・長い記事の目次」の4点に対応しています。スマホでもご確認ください。
      </p>
      <ol className="mt-8 grid gap-4">
        {(Object.keys(PREVIEW_VARIANTS) as Variant[]).map((key) => {
          const v = PREVIEW_VARIANTS[key];
          return (
            <li key={key}>
              <Link
                href={`/article-preview/${key}`}
                className="group block rounded-2xl border border-line-strong p-5 transition-colors hover:border-ink sm:p-6"
              >
                <span className="flex items-baseline gap-3">
                  <span className="text-[1.25rem] font-black text-ink group-hover:underline">{v.name}</span>
                  <span aria-hidden className="ml-auto text-muted">→</span>
                </span>
                <span className="mt-1.5 block text-[15px] font-medium leading-[1.8] text-ink">{v.desc}</span>
                <ul className="mt-3 grid gap-1 text-[13.5px] leading-[1.75] text-ink-soft">
                  {v.points.map((p) => (
                    <li key={p}>・{p}</li>
                  ))}
                </ul>
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
