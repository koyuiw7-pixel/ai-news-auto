import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import AffiliateBox from "@/components/AffiliateBox";
import {
  formatDate,
  getAllArticles,
  getAllTags,
  type AffiliateLink,
  type Article,
} from "@/lib/articles";

type Props = {
  current?: Article;
  affiliates?: AffiliateLink[];
};

export default function Sidebar({ current, affiliates = [] }: Props) {
  const latest = getAllArticles()
    .filter((a) => a.slug !== current?.slug)
    .slice(0, 5);
  const tags = getAllTags().slice(0, 14);

  return (
    <div className="space-y-8 lg:sticky lg:top-20">
      {/* サイドバー最上部の広告枠 */}
      <AdSlot position="sidebar" />

      {affiliates.length > 0 && <AffiliateBox links={affiliates} compact />}

      {latest.length > 0 && (
        <section className="rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-sm font-bold text-ink">最新記事</h2>
          <ul className="mt-4 space-y-4">
            {latest.map((article) => (
              <li key={article.slug}>
                <Link href={`/articles/${article.slug}`} className="group block">
                  <span className="text-xs text-muted">
                    {formatDate(article.publishedAt)}
                  </span>
                  <span className="mt-1 block text-sm font-medium leading-snug text-ink-soft group-hover:text-accent">
                    {article.title}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tags.length > 0 && (
        <section className="rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-sm font-bold text-ink">トピック</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {tags.map((tag) => (
              <Link
                key={tag.slug}
                href={`/tags/${tag.slug}`}
                className="rounded-full bg-surface-2 px-2.5 py-1 text-xs text-muted hover:bg-accent-soft hover:text-accent"
              >
                #{tag.label}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
