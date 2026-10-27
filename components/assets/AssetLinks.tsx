import Link from "next/link";
import type { ArticleSummary } from "@/lib/articles";
import { eventForArticle, eventStatus } from "@/lib/events";
import { isPricingSource } from "@/lib/pricing";

const PRICE_RE = /\d/;
const AI_PRODUCT_RE = /ChatGPT|GPT-|Claude|Opus|Sonnet|Fable|Gemini|Grok|Copilot|DeepSeek|Kimi|Llama|Mistral|API/i;

/**
 * 記事から定番ページへの控えめな案内（料金の記事 → 早見表、イベント中の記事 → イベントページ）。
 * 当てはまるものが無ければ何も出さない。
 */
export default function AssetLinks({ article }: { article: ArticleSummary }) {
  const verdictPrice = article.verdict?.price ?? "";
  const pricing =
    isPricingSource(article.slug) ||
    (article.genreSlug === "ai" && PRICE_RE.test(verdictPrice) && AI_PRODUCT_RE.test(`${article.title} ${verdictPrice}`));
  const event = eventForArticle(article);
  if (!pricing && !event) return null;

  const link = "font-bold text-ink underline decoration-line-strong underline-offset-[3px] hover:decoration-ink";
  return (
    <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-meta text-ink-soft">
      {event && (
        <span>
          <Link href={`/events/${event.slug}`} className={link}>
            {event.nameJa}の{eventStatus(event) === "upcoming" ? "日程（日本時間）" : "発表内容まとめ"}
          </Link>
        </span>
      )}
      {pricing && (
        <span>
          他のAIと料金を比べる：
          <Link href="/ai-pricing" className={link}>
            AIの料金・日本対応 早見表
          </Link>
        </span>
      )}
    </p>
  );
}
