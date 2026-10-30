import fs from "@/lib/content-fs";
import path from "node:path";
import { getAllArticles, type ArticleSummary } from "@/lib/articles";

/**
 * 使い方ガイド（content/howto/*.json、scripts/evergreen.py が作る。URL は /guides/<slug>）。
 *
 * 「ChatGPT 使い方」「Gemini 無料 どこまで」のように長く検索される疑問に、公式ページだけを根拠に答える。
 * 公式ページは14日ごと（料金などの関連ニュースが出たときはすぐ）に確認し直し、確認日（checkedAt）を更新する。
 */
export type HowtoGuide = {
  slug: string;
  tool: string;
  toolName: string;
  company: string;
  intent: string;
  keyword: string;
  title: string;
  seoTitle: string;
  description: string;
  conclusion: string[];
  intro: string;
  steps: { title: string; body: string; commands?: string[] }[];
  pricing: { plan: string; price: string; note?: string }[];
  freeTier: string[];
  japan: { answer: string; body: string };
  tips: { title: string; body: string }[];
  faq: { q: string; a: string }[];
  /** 関連ニュースを見つける正規表現（見出しと短い題名に照合） */
  match: string;
  /** 関連する製品のまとめページ（content/products）の slug */
  products: string[];
  sources: { url: string; title: string; checkedAt: string }[];
  createdAt: string;
  updatedAt: string;
  /** 公式ページで内容を確かめた日時（確認日） */
  checkedAt: string;
  /** 手動編集した広告・応募記事の開示。設定した記事だけ冒頭に表示する。 */
  disclosure?: string;
  /** 自動生成・別AI照合・定期更新の定型説明に代わる、実際の編集方法。 */
  editorialNote?: string;
  officialAction?: { url: string; label: string };
  /** 回答を読んだあとに案内する選び方ガイド。既存の有効なslugだけ表示する。 */
  decisionGuideSlug?: string;
};

// 文字列で組み立てて、content/ 全体をサーバー関数に同梱させない（lib/articles.ts と同じ理由）
const HOWTO_DIR = [process.cwd(), "content", "howto"].join(path.sep);

let cache: HowtoGuide[] | null = null;

/** 新しい順 */
export function getAllHowtos(): HowtoGuide[] {
  if (cache) return cache;
  if (!fs.existsSync(HOWTO_DIR)) return (cache = []);
  cache = fs
    .readdirSync(HOWTO_DIR)
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) => {
      try {
        const data = JSON.parse(fs.readFileSync(/* turbopackIgnore: true */ `${HOWTO_DIR}${path.sep}${file}`, "utf8")) as HowtoGuide;
        return data.slug && data.steps?.length ? [data] : [];
      } catch {
        return [];
      }
    })
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return cache;
}

export function getHowto(slug: string): HowtoGuide | undefined {
  return getAllHowtos().find((guide) => guide.slug === slug);
}

const newsCache = new Map<string, ArticleSummary[]>();

/** ガイドの題材に関係する AI 記事（新しい順） */
export function howtoArticles(guide: HowtoGuide): ArticleSummary[] {
  const cached = newsCache.get(guide.slug);
  if (cached) return cached;
  let pattern: RegExp;
  try {
    pattern = new RegExp(guide.match);
  } catch {
    return [];
  }
  const articles = guide.match
    ? getAllArticles().filter(
        (article) => article.genreSlug === "ai" && pattern.test(`${article.title} ${article.seoTitle ?? ""}`),
      )
    : [];
  newsCache.set(guide.slug, articles);
  return articles;
}

/** 製品のまとめページから案内する使い方ガイド */
export function howtosForProduct(productSlug: string): HowtoGuide[] {
  return getAllHowtos().filter((guide) => guide.products.includes(productSlug));
}

/** 同じ題材（ツール）のほかのガイド */
export function siblingHowtos(guide: HowtoGuide, limit = 6): HowtoGuide[] {
  return getAllHowtos()
    .filter((other) => other.slug !== guide.slug && other.tool === guide.tool)
    .concat(getAllHowtos().filter((other) => other.slug !== guide.slug && other.tool !== guide.tool))
    .slice(0, limit);
}

/** 記事の見出しに題材が出てくるガイド（記事ページから1行だけ案内する） */
export function howtoForArticle(article: ArticleSummary): HowtoGuide | undefined {
  const text = `${article.title} ${article.seoTitle ?? ""}`;
  return getAllHowtos().find((guide) => {
    try {
      return guide.match && new RegExp(guide.match).test(text);
    } catch {
      return false;
    }
  });
}
