import type { Metadata } from "next";
import Link from "next/link";
import Timeline from "@/components/Timeline";
import VerdictBadge from "@/components/VerdictBadge";
import { getAllArticles } from "@/lib/articles";
import { usability, verdictOf } from "@/lib/verdict";
import { siteConfig } from "@/site.config";

const TITLE = "今すぐ使える最新AIツール・新機能まとめ【毎日更新】";
const DESCRIPTION =
  "発表されたばかりのAIの新機能・新モデルのうち、今日から使えるものだけを集めた一覧です。日本から使えるか・料金・無料で試せるかを、発表ごとに判定しています。";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/usable" },
  openGraph: { title: TITLE, description: DESCRIPTION, url: "/usable" },
};

/**
 * 「使えるかどうか」の判定で絞り込んだハブページ。
 * 「最新 AI ツール」「今使える AI」のような検索と、AI検索からの引用の受け皿にする。
 */
export default function UsablePage() {
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai");
  const usable = ai.filter((a) => {
    const verdict = verdictOf(a);
    return verdict && usability(verdict) === "go";
  });
  const soon = ai.filter((a) => verdictOf(a)?.status === "soon").slice(0, 8);
  const free = usable.filter((a) => verdictOf(a)?.free === true).length;
  const updatedAt = usable[0]?.generatedAt;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: TITLE,
    description: DESCRIPTION,
    numberOfItems: Math.min(usable.length, 30),
    itemListElement: usable.slice(0, 30).map((article, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: `${siteConfig.url}/articles/${article.slug}`,
      name: article.seoTitle || article.title,
    })),
  };

  return (
    <div className="mx-auto max-w-[920px] px-5 py-10 sm:px-8 sm:py-14">
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <p className="flex items-center gap-2 text-[12px] font-bold text-muted">
        <VerdictBadge kind="go" />
        {updatedAt && (
          <span className="index-num">
            {new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", timeZone: "Asia/Tokyo" }).format(Date.parse(updatedAt))}更新
          </span>
        )}
      </p>
      <h1 className="display mt-3 text-[1.9rem] leading-tight text-balance sm:text-[2.4rem]">{TITLE}</h1>
      <p className="mt-4 max-w-[60ch] text-[15px] leading-[1.9] text-ink-soft">{DESCRIPTION}</p>

      <dl className="mt-6 grid max-w-[520px] grid-cols-3 overflow-hidden rounded-2xl border border-line">
        {[
          { label: "今すぐ使える発表", value: `${usable.length}本` },
          { label: "うち無料で試せる", value: `${free}本` },
          { label: "判定した発表", value: `${ai.filter((a) => verdictOf(a)).length}本` },
        ].map((item, index) => (
          <div key={item.label} className={`px-4 py-3 ${index > 0 ? "border-l border-line" : ""}`}>
            <dt className="text-[11px] text-muted">{item.label}</dt>
            <dd className="index-num mt-0.5 text-[20px] font-bold text-ink">{item.value}</dd>
          </div>
        ))}
      </dl>

      <section aria-labelledby="usable-list" className="mt-12">
        <h2 id="usable-list" className="display mb-3 text-[1.4rem]">
          今日から使えるもの
        </h2>
        <Timeline articles={usable.slice(0, 40)} />
      </section>

      {soon.length > 0 && (
        <section aria-labelledby="soon-list" className="mt-14">
          <h2 id="soon-list" className="display mb-3 text-[1.4rem]">
            もうすぐ使えるもの
          </h2>
          <Timeline articles={soon} />
        </section>
      )}

      <p className="mt-12 rounded-2xl bg-surface px-5 py-4 text-[12px] leading-relaxed text-muted">
        判定は各発表の時点の情報にもとづきます。提供地域・料金は変わることがあるため、最新の状況は各社の公式情報をご確認ください。
        <Link href="/about" className="ml-1 underline">
          判定の方法について
        </Link>
      </p>
    </div>
  );
}
