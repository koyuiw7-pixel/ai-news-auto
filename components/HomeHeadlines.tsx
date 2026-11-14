import Link from "next/link";
import type { ArticleSummary } from "@/lib/articles";
import { displayHeadline } from "@/lib/headline";

/**
 * トップの主役のすぐ下に並べる「暮らしとお金」の見出し（写真なし・文字だけ。2026-11-11 読者目線レビュー 1位・2位）。
 * スマホの最初の画面に見出しが主役の1本しかなかった（Yahoo!ニュースは6本）。日経電子版のスマホのように、細い線で区切った太字の見出しだけを並べる。
 * 記事は lib/home-lead.ts の pickHomeHeadlines（分野・題名・読まれた回数で決める）
 */
export default function HomeHeadlines({ articles, label = "暮らしとお金の主なニュース" }: { articles: ArticleSummary[]; label?: string }) {
  if (articles.length === 0) return null;
  return (
    <section aria-labelledby="top-headlines-heading" data-home-zone="headlines" className="mt-4 sm:mt-10">
      <h2 id="top-headlines-heading" className="flex items-center gap-2 text-[1.25rem] font-bold leading-[1.4] text-ink">
        <span aria-hidden className="h-5 w-[3px] rounded-full bg-live" />
        {label}
      </h2>
      <ul className="mt-1 sm:mt-3 sm:grid sm:grid-cols-2 sm:gap-x-8 lg:grid-cols-3">
        {articles.map((article) => (
          <li key={article.slug} className="border-b border-line">
            <Link
              href={`/articles/${article.slug}`}
              className="line-clamp-2 py-2.5 text-[15.5px] font-bold leading-[1.5] text-ink underline-offset-4 hover:underline sm:py-3"
            >
              {displayHeadline(article.title)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
