import type { Metadata } from "next";
import RailPicker from "@/components/rail/RailPicker";
import RailRanking from "@/components/rail/RailRanking";
import RailShop from "@/components/rail/RailShop";
import { getAllArticles } from "@/lib/articles";
import { offerForArticle } from "@/lib/offers";

export const metadata: Metadata = {
  title: "右側PR枠の比較",
  robots: { index: false, follow: false },
};

const SAMPLES = ["local", "voice", "claude"];
const LABEL: Record<string, string> = { local: "GPU・PCの記事", voice: "音声AIの記事", claude: "Claudeの記事" };

/** 記事ページ右側（PC）の商品枠を3案で見比べるための確認ページ。検索には出さない */
export default function PrLabPage() {
  const articles = getAllArticles().filter((a) => a.genreSlug === "ai");
  const samples = SAMPLES.map((topic) => {
    for (const article of articles) {
      const offer = offerForArticle(article);
      if (offer?.topic === topic) return { topic, article, offer };
    }
    return undefined;
  }).filter((x) => x !== undefined);

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-10 sm:px-8">
      <h1 className="display text-[1.8rem]">右側のPR枠：3案の比較</h1>
      <p className="mt-2 text-[14px] text-muted">
        記事ページのPC表示で右側に出る枠です。実際の幅（320px）・実際の商品で並べています。どれも記事を読み進めても右側に付いてきます。
      </p>

      {samples.map(({ topic, article, offer }) => (
        <section key={topic} className="mt-12">
          <h2 className="text-[15px] font-bold">
            {LABEL[topic]}<span className="ml-2 text-[13px] font-normal text-muted">例：{article.title}</span>
          </h2>
          <div className="mt-4 grid gap-8 overflow-x-auto lg:grid-cols-3">
            {[
              { name: "A 商品ページ型", node: <RailShop offer={offer} /> },
              { name: "B ランキング型", node: <RailRanking offer={offer} /> },
              { name: "C 切り替え型", node: <RailPicker offer={offer} /> },
            ].map(({ name, node }) => (
              <div key={name}>
                <p className="mb-2 text-[13px] font-bold text-ink-soft">{name}</p>
                <div className="w-[320px] max-w-full">{node}</div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
