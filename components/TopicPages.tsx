import Link from "next/link";
import { articleTitle } from "@/lib/headline";
import { getAllArticles, type ArticleSummary } from "@/lib/articles";
import { topicPages } from "@/lib/related";

/**
 * 記事の終わりの「この話題のページ」（SEO A17）。同じ話題で別の疑問（対象か・手続き・家族の分など）に答えるページの一覧。
 * 元の記事にも角度の記事にも出す。見出しは記事の章ではないので h2 にしない。無ければ何も出さない
 */
export default function TopicPages({ article, className = "" }: { article: ArticleSummary; className?: string }) {
  const { parent, pages } = topicPages(article, getAllArticles());
  const items = [...(parent ? [parent] : []), ...pages];
  if (items.length === 0) return null;
  return (
    <nav aria-label="この話題のページ" className={`border-l-4 border-accent bg-surface px-5 py-4 ${className}`} data-topic-pages>
      <p className="text-note font-bold text-ink">この話題のページ</p>
      <ul className="mt-2 grid gap-2">
        {items.map((a) => (
          <li key={a.slug} className="text-note leading-relaxed">
            <Link href={`/articles/${a.slug}`} className="font-semibold text-ink underline decoration-line-strong underline-offset-4 hover:text-accent">
              {articleTitle(a)}
            </Link>
            {parent && a.slug === parent.slug && <span className="ml-1 text-muted">（全体の解説）</span>}
          </li>
        ))}
      </ul>
    </nav>
  );
}
