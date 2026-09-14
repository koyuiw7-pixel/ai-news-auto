import Link from "next/link";
import type { Article } from "@/lib/articles";

const shortDate = new Intl.DateTimeFormat("ja-JP", {
  month: "2-digit",
  day: "2-digit",
  timeZone: "Asia/Tokyo",
});

/**
 * 速報ティッカー。点の色で情報の種類を示す（琥珀＝公式発表、シアン＝まとめ記事）。
 * 途切れず流すため同じ列を2回並べ、2回目は読み上げ・フォーカスの対象から外す。
 * マウスを乗せる／フォーカスすると止まり、動きを減らす設定では流れない。
 */
export default function Ticker({ items }: { items: Article[] }) {
  if (items.length === 0) return null;

  const row = (duplicate: boolean) =>
    items.map((article) => (
      <Link
        key={`${duplicate ? "dup-" : ""}${article.slug}`}
        href={`/articles/${article.slug}`}
        className="ticker-item"
        aria-hidden={duplicate || undefined}
        tabIndex={duplicate ? -1 : undefined}
      >
        <i
          className={`dot ${article.type === "roundup" ? "dot-roundup" : "dot-official"}`}
          aria-hidden
        />
        <time dateTime={article.publishedAt} className="index-num">
          {shortDate.format(new Date(article.publishedAt)).replace("/", ".")}
        </time>
        <span>
          {article.type === "roundup" ? "まとめ：" : ""}
          {article.title}
        </span>
      </Link>
    ));

  return (
    <div className="ticker" aria-label="最新の見出し">
      <div className="ticker-track">
        {row(false)}
        {row(true)}
      </div>
    </div>
  );
}
