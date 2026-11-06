import Link from "next/link";
import { listsForArticle } from "@/lib/topic-lists";

/** 記事のページの「この一覧に載っています」（台帳 A52）。載っていなければ何も出さない */
export default function TopicListMembership({ slug, className = "" }: { slug: string; className?: string }) {
  const lists = listsForArticle(slug);
  if (lists.length === 0) return null;
  return (
    <p className={`text-note text-ink-soft ${className}`} data-topic-membership>
      この記事は{" "}
      {lists.map((m, i) => (
        <span key={m.kind}>
          {i > 0 && "・"}
          <Link href={`/roundups/${m.kind}`} className="font-semibold text-accent underline underline-offset-4">「{m.heading}」</Link>
        </span>
      ))}
      {" "}に載っています。
    </p>
  );
}
