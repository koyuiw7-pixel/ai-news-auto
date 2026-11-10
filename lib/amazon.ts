import type { ArticleSummary } from "@/lib/articles";

/**
 * 製品を扱う記事に1つだけ出す「Amazon / 楽天で見る」のテキストリンク。
 * Amazonアソシエイト（PA-API なし）なので、価格・商品画像は出さず、検索リンクだけを使う
 * （ASIN は商品ページで確かめたものだけ。在庫切れ・型番違いを避けるため基本は検索）。
 * 楽天は scripts/rakuten_books.py と同じ A8 経由の楽天リンクで、同じ語の検索結果へ飛ばす。
 */

export const AMAZON_TAG = "saisokuai-22";

// A8.net「楽天アフィリエイト」提携のID（scripts/rakuten_books.py と同じ）
const A8MAT = "4BELTP+50ED2Q+2HOM+BWGDT";
const RAKUTEN_HGC = "g00q0724.2bo11c45.g00q0724.2bo12179/a26102173090_4BELTP_50ED2Q_2HOM_BWGDT";

type Rule = {
  /** 題名（seoTitle 含む）に出てくる語 */
  match: RegExp;
  /** 題名にあれば出さない（ソフト更新・脆弱性など、製品そのものの記事でないもの） */
  exclude?: RegExp;
  /** 表示名 */
  name: string;
  /** 検索語（Amazon・楽天で共通） */
  query: string;
  /** 商品ページで確かめた ASIN（あれば検索より優先） */
  asin?: string;
};

// 上から順に見て、最初に当たったものを使う（細かい製品名を先に）
const RULES: Rule[] = [
  // 冬の暖房（電気代・燃料代を比べた記事）。リコール・事故の記事には出さない（2026-11-10）
  { match: /電気(しき|敷き|かけ|掛け)?毛布/, exclude: /リコール|回収|発火|発煙|事故|火災/, name: "電気毛布", query: "電気毛布" },
  { match: /こたつ/, exclude: /リコール|回収|発火|発煙|事故|火災/, name: "こたつ", query: "こたつ" },
  { match: /ホットカーペット/, exclude: /リコール|回収|発火|発煙|事故|火災/, name: "ホットカーペット", query: "ホットカーペット" },
  { match: /石油(ファン)?ヒーター|石油ストーブ/, exclude: /リコール|回収|発火|発煙|事故|火災/, name: "石油ファンヒーター", query: "石油ファンヒーター" },
  { match: /iPhone/i, exclude: /iOS|Siri|更新|アップデート|脆弱性|修正/, name: "iPhone", query: "Apple iPhone" },
  { match: /iPad\s?mini/i, name: "iPad mini", query: "Apple iPad mini" },
  { match: /iPad\s?Pro/i, name: "iPad Pro", query: "Apple iPad Pro" },
  { match: /iPad\s?Air/i, name: "iPad Air", query: "Apple iPad Air" },
  { match: /iPad/i, exclude: /iPadOS/, name: "iPad", query: "Apple iPad" },
  { match: /MacBook\s?Pro/i, name: "MacBook Pro", query: "Apple MacBook Pro" },
  { match: /MacBook\s?Air/i, name: "MacBook Air", query: "Apple MacBook Air" },
  { match: /iMac/, name: "iMac", query: "Apple iMac" },
  { match: /Mac\s?Studio/i, name: "Mac Studio", query: "Apple Mac Studio" },
  { match: /Mac\s?mini/i, name: "Mac mini", query: "Apple Mac mini" },
  { match: /AirPods/i, name: "AirPods", query: "Apple AirPods" },
  { match: /Apple\s?Watch/i, exclude: /watchOS/, name: "Apple Watch", query: "Apple Watch" },
  { match: /Galaxy\s?Buds/i, name: "Galaxy Buds", query: "Galaxy Buds" },
  { match: /Galaxy\s?(S|Z|A)\s?\d|Galaxy\s?Tab|Galaxy\s?Watch/i, name: "Galaxy", query: "Samsung Galaxy" },
  { match: /Pixel\s?Watch/i, name: "Pixel Watch", query: "Google Pixel Watch" },
  { match: /Pixel\s?Buds/i, name: "Pixel Buds", query: "Google Pixel Buds" },
  { match: /Pixel\s?Tag|紛失防止タグ/i, name: "紛失防止タグ", query: "紛失防止タグ" },
  { match: /Pixel\s?\d+/i, name: "Pixel", query: "Google Pixel" },
  { match: /Switch\s?2/i, name: "Nintendo Switch 2", query: "Nintendo Switch 2" },
  { match: /Nintendo\s?Switch|ニンテンドースイッチ/i, name: "Nintendo Switch", query: "Nintendo Switch" },
  { match: /PS5|PlayStation\s?5|プレイステーション5/i, name: "PlayStation 5", query: "PlayStation 5" },
  { match: /ゲーミングPC/i, name: "ゲーミングPC", query: "ゲーミングPC" },
  { match: /RTX\s?50[5-9]0/i, exclude: /Spark/i, name: "GeForce RTX 50シリーズ", query: "GeForce RTX 5090" },
  { match: /ゲーミングモニター/, name: "ゲーミングモニター", query: "ゲーミングモニター" },
  { match: /(4K|有機EL|PC|USB-C)モニター/i, name: "PCモニター", query: "PCモニター" },
  { match: /空間再現ディスプレイ/, name: "空間再現ディスプレイ", query: "ソニー 空間再現ディスプレイ" },
  { match: /(ワイヤレス|メカニカル|ゲーミング)?キーボード/, exclude: /ソフトウェアキーボード|IME|入力アプリ/, name: "キーボード", query: "キーボード" },
  { match: /(ワイヤレス|ゲーミング)マウス/, name: "マウス", query: "ワイヤレスマウス" },
  { match: /Kindle/i, name: "Kindle", query: "Kindle 端末" },
  { match: /(AI|生成AI|ChatGPT).{0,12}(書籍|新刊|著書)|(書籍|新刊|著書).{0,12}(AI|生成AI|ChatGPT)/i, name: "生成AIの本", query: "生成AI 本" },
];

// 製品を紹介する記事だけ（投資の分析・行政のお知らせなどには出さない）
const GENRES = new Set(["ai", "tech-gadget", "entertainment", "lifestyle", "business"]);

export type ShopLink = {
  name: string;
  query: string;
  amazon: string;
  rakuten: string;
};

export function amazonUrl(rule: Pick<Rule, "query" | "asin">): string {
  return rule.asin
    ? `https://www.amazon.co.jp/dp/${rule.asin}?tag=${AMAZON_TAG}`
    : `https://www.amazon.co.jp/s?k=${encodeURIComponent(rule.query)}&tag=${AMAZON_TAG}`;
}

/** A8 の楽天リンクと同じ形で、楽天市場の検索結果へ飛ばす */
export function rakutenSearchUrl(query: string): string {
  return rakutenPageUrl(`https://search.rakuten.co.jp/search/mall/${encodeURIComponent(query)}/`);
}

/** 楽天ふるさと納税のトップ（2026-11-10 に event.rakuten.co.jp で確かめた公式のURL） */
export const RAKUTEN_FURUSATO_PAGE = "https://event.rakuten.co.jp/furusato/";

/**
 * A8 の楽天リンク（rakutenSearchUrl・scripts/rakuten_books.py と同じ a8mat と hgc）で、楽天の決まったページへ飛ばす。
 * 同じ形を scripts/a8_import.py の RAKUTEN_DEEPLINKS が offers.json に書く（tests/test_rakuten_furusato.cjs が一致を確かめる）
 */
export function rakutenPageUrl(page: string): string {
  const inner = `https://hb.afl.rakuten.co.jp/hgc/${RAKUTEN_HGC}?pc=${encodeURIComponent(page)}&m=${encodeURIComponent(page)}`;
  return `https://rpx.a8.net/svt/ejp?a8mat=${A8MAT}&rakuten=y&a8ejpredirect=${encodeURIComponent(inner)}`;
}

/** 記事が特定の製品（カテゴリ）を扱っていれば、その買い物リンクを返す */
export function shopLinkForArticle(article: Pick<ArticleSummary, "title" | "seoTitle" | "genreSlug">): ShopLink | undefined {
  if (!GENRES.has(article.genreSlug)) return undefined;
  const title = `${article.title} ${article.seoTitle ?? ""}`;
  const rule = RULES.find((r) => r.match.test(title) && !r.exclude?.test(title));
  if (!rule) return undefined;
  return { name: rule.name, query: rule.query, amazon: amazonUrl(rule), rakuten: rakutenSearchUrl(rule.query) };
}
