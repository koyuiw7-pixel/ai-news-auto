import Link from "next/link";
import type { Article } from "@/lib/articles";

const shortDate = new Intl.DateTimeFormat("ja-JP", {
  month: "2-digit",
  day: "2-digit",
  timeZone: "Asia/Tokyo",
});

const dateTime = new Intl.DateTimeFormat("ja-JP", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Tokyo",
});

type Props = {
  items: Article[];
  /** 最後に記事を生成した日時（ISO） */
  updatedAt?: string;
  /** 直近24時間に追加した本数 */
  recentCount?: number;
};

/**
 * 速報ティッカー。
 * 左に「最終更新」を固定表示し、いま動いているサイトだと一目で分かるようにする。
 * 点の色は情報の種類（琥珀＝公式発表、シアン＝まとめ記事）。
 * マウスを乗せる／フォーカスすると止まり、動きを減らす設定では流れない。
 */
export default function Ticker({ items, updatedAt, recentCount = 0 }: Props) {
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
    <div className="ticker">
      {updatedAt && (
        <p className="ticker-label">
          <span className="relative flex size-2" aria-hidden>
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-official opacity-60 motion-reduce:animate-none" />
            <span className="relative inline-flex size-2 rounded-full bg-official" />
          </span>
          <span>
            最終更新 <time dateTime={updatedAt} className="index-num">{dateTime.format(new Date(updatedAt))}</time>
          </span>
          {recentCount > 0 && (
            <span className="hidden font-medium text-muted sm:inline">・24時間で{recentCount}本</span>
          )}
        </p>
      )}
      <div className="ticker-viewport" aria-label="最新の見出し">
        <div className="ticker-track">
          {row(false)}
          {row(true)}
        </div>
      </div>
    </div>
  );
}
