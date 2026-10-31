import fs from "@/lib/content-fs";
import path from "node:path";
import { getArticleSummary, type ArticleSummary } from "@/lib/articles";

/**
 * 製品ごとのまとめページ（content/products/*.json、scripts/products.py が作る）。
 *
 * ニュースは数日で読まれなくなるが、「〇〇とは」「料金」「日本で使える？」は長く検索される。
 * 中身はすべて自サイトの記事から取った事実で、項目ごとに出典の記事 slug を持つ。
 */
export type Sourced = { text: string; sources: string[] };

export type Product = {
  slug: string;
  name: string;
  aliases: string[];
  /** lib/companies.ts の slug（色・企業ページがない企業は "other"） */
  company: string;
  companyName: string;
  category: string;
  overview: Sourced;
  facts: { label: string; value: string; sources: string[] }[];
  capabilities: Sourced[];
  pricing: Sourced[];
  japan: Sourced[];
  howto: Sourced[];
  differences: Sourced[];
  faq: { q: string; a: string; sources: string[] }[];
  timeline: { date: string; slug: string; event: string }[];
  /** 関連する製品の slug */
  related: string[];
  /** 関係する記事（新しい順） */
  articles: string[];
  /** この製品のまとめページへ案内する記事 */
  linkFrom: string[];
  createdAt: string;
  updatedAt: string;
  officialCheck?: { date: string; url: string; label: string };
};

/** 自動再生成より優先する、公式資料で確認した編集部の訂正。 */
function editorialCorrections(product: Product): Product {
  if (product.slug === "meta-muse") {
    return {
      ...product,
      category: "アプリ・サービス",
      overview: { text: "Museは、買い物や旅行の下調べなどを手伝うMetaの個人向けAIエージェントです。", sources: ["meta-muse-singapore-launch"] },
      facts: [
        { label: "提供状況", value: "シンガポールで提供。日本向けの提供はこの発表では確認できません", sources: ["meta-muse-singapore-launch"] },
        { label: "料金", value: "シンガポールでは大半の用途が無料。有料プランもあります", sources: ["meta-muse-singapore-launch"] },
        { label: "利用環境", value: "シンガポールではiOS・Android・Webで提供", sources: ["meta-muse-singapore-launch"] },
      ],
      capabilities: [
        { text: "提携サービスを通じた買い物の比較や旅行・予約候補の検索を支援します。連携機能は順次提供されます。", sources: ["meta-muse-singapore-launch"] },
        { text: "メールや購入などの重要な操作の前に確認する設計です。", sources: ["meta-muse-singapore-launch"] },
      ],
      pricing: [{ text: "シンガポールでは大半の用途が無料で、有料プランもあります。", sources: ["meta-muse-singapore-launch"] }],
      japan: [{ text: "シンガポール向け公式発表には、日本での提供時期は記載されていません。", sources: ["meta-muse-singapore-launch"] }],
      howto: [{ text: "シンガポールではiOS、Android、muse.aiで提供されています。", sources: ["meta-muse-singapore-launch"] }],
      differences: [], faq: [],
      officialCheck: { date: "2026-10-31", url: "https://about.fb.com/news/2026/10/muse-is-now-available-in-singapore-the-worlds-first-personal-ai-agent-built-for-everyone/", label: "Meta公式：シンガポールでの提供" },
    };
  }
  if (product.slug !== "openai-dot") return product;
  const source = "chatgpt-mobile-dot-setup";
  return {
    ...product,
    category: "アプリ・サービス",
    overview: { text: "OpenAIのdotは、ChatGPTで目標を伝えると、接続したアプリや専用の環境を使って調査や作業を進めるAIエージェントです。", sources: [source] },
    facts: [
      { label: "対象", value: "対象地域の18歳以上のPro、対象のBusiness Premium。Enterpriseなどは管理者によるベータ有効化が必要", sources: [] },
      { label: "料金", value: "最初の1体は対象プランに含まれます。より深い作業には利用枠があります", sources: [] },
      { label: "提供状況", value: "段階的に提供中。アカウントに届くまで数日かかる場合があります", sources: [] },
    ],
    capabilities: [
      { text: "接続を許可したアプリを使って、調査、資料作成、作業の整理などを進めます。", sources: [] },
      { text: "旅行手配のような用途もデモされています。購入や共有などの重要な操作は設定と確認条件を確かめてください。", sources: [] },
    ],
    pricing: [{ text: "最初のdotは対象プランに追加料金なしで含まれます。深い作業にはプランごとの利用枠があります。", sources: [] }],
    japan: [{ text: "提供対象はプラン、年齢、地域、組織の設定によって異なります。アカウントに表示される案内を確認してください。", sources: [] }],
    howto: [{ text: "対象アカウントではChatGPTのモバイルアプリ、デスクトップアプリ、デスクトップ版Webから設定を始められます。", sources: [] }],
    differences: [], faq: [],
    officialCheck: { date: "2026-10-31", url: "https://help.openai.com/en/articles/20001530-getting-started-with-your-dot", label: "OpenAI公式：dotの利用条件と設定" },
  };
}

// 文字列で組み立てて、content/ 全体をサーバー関数に同梱させない（lib/articles.ts と同じ理由）
const PRODUCTS_DIR = [process.cwd(), "content", "products"].join(path.sep);

let cache: Product[] | null = null;

/** 関係する記事の多い順 */
export function getAllProducts(): Product[] {
  if (cache) return cache;
  if (!fs.existsSync(PRODUCTS_DIR)) return (cache = []);
  cache = fs
    .readdirSync(PRODUCTS_DIR)
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) => {
      try {
        const data = JSON.parse(fs.readFileSync(/* turbopackIgnore: true */ `${PRODUCTS_DIR}${path.sep}${file}`, "utf8")) as Product;
        return data.slug && data.overview?.text ? [editorialCorrections(data)] : [];
      } catch {
        return [];
      }
    })
    .sort((a, b) => b.articles.length - a.articles.length || a.name.localeCompare(b.name));
  return cache;
}

export function getProduct(slug: string): Product | undefined {
  return getAllProducts().find((p) => p.slug === slug);
}

let byArticle: Map<string, Product> | null = null;

/** 記事から案内するまとめページ（題名でいちばん手前に出てくる製品。1記事に1つ） */
export function productForArticle(articleSlug: string): Product | undefined {
  if (!byArticle) {
    byArticle = new Map();
    for (const product of getAllProducts()) {
      for (const slug of product.linkFrom ?? []) if (!byArticle.has(slug)) byArticle.set(slug, product);
    }
  }
  return byArticle.get(articleSlug);
}

/** 企業ページに出す製品（関係する記事の多い順） */
export function productsByCompany(company: string): Product[] {
  return getAllProducts().filter((p) => p.company === company);
}

/** 関係する記事（索引にある記事だけ。新しい順） */
export function productArticles(product: Product): ArticleSummary[] {
  return product.articles.map((slug) => getArticleSummary(slug)).filter((a): a is ArticleSummary => Boolean(a));
}

/** 料金・日本での提供がわかる製品か（題名の言い方を変える） */
export function hasBuyingInfo(product: Product): boolean {
  // 「未発表」だけの料金は、料金がわかる製品として扱わない（研究段階の製品など）
  return product.pricing.length > 0 || product.facts.some((f) => f.label === "料金" && !/未発表|未定|不明|なし/.test(f.value));
}

/** 検索結果の題名 */
export function productSeoTitle(product: Product): string {
  return hasBuyingInfo(product)
    ? `${product.name}とは？料金・使い方・日本で使えるか【最新】`
    : `${product.name}とは？できること・これまでの流れ【最新】`;
}

/** ページの見出し（【最新】は検索結果用なので付けない） */
export function productHeading(product: Product): string {
  return hasBuyingInfo(product)
    ? `${product.name}とは？料金・使い方・日本で使えるか`
    : `${product.name}とは？できること・これまでの流れ`;
}

/** 同じ製品の古い製品ガイド（/guides/<slug>）は、まとめページへ転送する */
export function supersededGuideSlugs(guideSlugs: string[]): string[] {
  const slugs = new Set(getAllProducts().map((p) => p.slug));
  return guideSlugs.filter((slug) => slugs.has(slug));
}
