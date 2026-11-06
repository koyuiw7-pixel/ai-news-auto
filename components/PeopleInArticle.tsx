import Link from "next/link";
import type { ArticleSummary } from "@/lib/articles";
import { peopleInArticle } from "@/lib/people";

/** 記事に出てくる人物のまとめページへのリンク（台帳 A53）。いなければ何も出さない */
export default function PeopleInArticle({ article, className = "" }: { article: ArticleSummary; className?: string }) {
  const people = peopleInArticle(article);
  if (people.length === 0) return null;
  return (
    <p className={`text-note text-ink-soft ${className}`} data-people-links>
      この記事の人物：
      {people.map((p, i) => (
        <span key={p.slug}>
          {i > 0 && "・"}
          <Link href={`/people/${p.slug}`} className="font-semibold text-accent underline underline-offset-4">{p.nameJa}の経歴と最新ニュース</Link>
        </span>
      ))}
    </p>
  );
}
