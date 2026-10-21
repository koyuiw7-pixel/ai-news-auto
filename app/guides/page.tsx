import type { Metadata } from "next";
import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import { getCompany, OTHER } from "@/lib/companies";
import { getAllGuides, guideArticles } from "@/lib/guides";

export const metadata: Metadata = {
  title: "AI製品ガイド：できること・料金・使い方",
  description:
    "ChatGPT Work、GPT-6 Astra、Claude Opus 5.5など注目のAI製品を、できること・料金・使い方・よくある質問まで1ページずつ解説。関連ニュースは自動で更新されます。",
  alternates: { canonical: "/guides" },
};

/** 製品ガイドの一覧 */
export default function GuidesPage() {
  const guides = getAllGuides();
  return (
    <div className="mx-auto max-w-[920px] px-5 py-10 sm:px-8 sm:py-14">
      <p className="eyebrow">GUIDES</p>
      <h1 className="display mt-2 text-[1.9rem] sm:text-[2.4rem]">AI製品ガイド</h1>
      <p className="mt-3 max-w-[60ch] text-[14.5px] leading-[1.9] text-ink-soft">
        注目のAI製品を「何ができるか・いくらか・どう始めるか」で1ページずつ整理しました。関連ニュースは新しい発表があるたびに自動で更新されます。
      </p>
      <ul className="mt-10 grid gap-3 sm:grid-cols-2">
        {guides.map((guide) => {
          const company = getCompany(guide.companySlug) ?? OTHER;
          return (
            <li key={guide.slug}>
              <Link
                href={`/guides/${guide.slug}`}
                className="group flex h-full flex-col gap-3 rounded-2xl border border-line p-5 transition-colors hover:border-ink"
              >
                <span className="flex items-center gap-2 text-[12px]">
                  {company.slug !== OTHER.slug ? (
                    <CompanyMark company={company} size={18} withName />
                  ) : (
                    <span className="font-bold text-ink-soft">注目のAI</span>
                  )}
                  <span className="index-num ml-auto text-muted">関連 {guideArticles(guide).length}本</span>
                </span>
                <span className="text-[17px] font-bold leading-snug text-ink group-hover:underline">{guide.title}</span>
                <span className="line-clamp-2 text-[13.5px] leading-[1.75] text-ink-soft">{guide.summary[0]}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
