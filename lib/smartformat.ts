import { shareImageArticle } from "./sns-photo";
import { aiCreditText, figureCreditText, officialCreditText } from "./image-credit";
import { isOwnImage } from "./thumb-url";
import type { ImageCredit } from "./articles";

/**
 * スマートニュース（SmartFormat）のフィード専用の部品（2026-11-07 オーナー承認）。
 * 公式の仕様書・申請前チェックリスト・外部リンクガイドライン（publishers.smartnews.com/hc/ja）に合わせる。
 *
 * - サムネイル: 共有カードと同じ順（使える記事の写真 → 表紙用の AI のイメージ）。どちらも無ければ見出しのカバー
 * - 本文: 記事の写真を先頭に置き、AI のイメージなら「画像はイメージ（AI生成）」の札を写真のすぐ下に付ける
 * - リンク: 本文中は出典・参考の外部リンクだけ（1段落1本・本文全体で3本まで）。自サイトへの誘導リンク・広告は文字だけ残す。
 *   最後の段落の後は出典と編集方針の2本（ガイドラインの上限は3本）
 * - 本文の h1 は h2 に（記事の題名と並ばないように）。ボタン・フォーム・スクリプトは消す
 */

const SITE = "https://ai-tech-express.jp";

/** 本文中に残す外部リンクの上限（チェックツールは多いと「リンクが多い」と警告する） */
export const BODY_LINK_LIMIT = 3;

type PhotoInput = {
  slug: string;
  thumbnail: string;
  imageCredit?: ImageCredit;
  coverImage?: string;
  coverCredit?: ImageCredit;
  noPhoto?: boolean;
  heroOk?: boolean;
};

export type FeedPhoto = { url: string; caption: string; ai: boolean };

/** フリー素材の写真の注記（記事ページの ImageCredit と同じ文） */
function stockCreditText(credit?: ImageCredit): string | null {
  if (credit?.kind !== "stock" || !credit.creator) return null;
  const by = [credit.creator, credit.provider].filter(Boolean).join(" / ");
  const license = credit.license ? `（${credit.license}${credit.license.startsWith("CC BY") ? "・トリミング" : ""}）` : "";
  return `写真はイメージです。写真: ${by}${license}`;
}

/**
 * フィードに載せる写真と、その下に付ける注記。サイトで配信する写真（/img/…jpg）で、出典の注記が書けるものだけ。
 * 無ければ null（サムネイルは見出しのカバーに回し、本文には写真を置かない）
 */
export function feedPhoto(article: PhotoInput): FeedPhoto | null {
  if (article.noPhoto) return null;
  const a = shareImageArticle(article);
  if (!isOwnImage(a.thumbnail)) return null;
  const credit = a.imageCredit;
  const caption = aiCreditText(credit) ?? officialCreditText(credit) ?? figureCreditText(credit) ?? stockCreditText(credit);
  if (!caption) return null;
  return { url: a.thumbnail, caption, ai: credit?.kind === "ai" };
}

const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function photoFigure(photo: FeedPhoto, alt: string): string {
  return `<figure><img src="${escapeHtml(photo.url)}" alt="${escapeHtml(alt)}" /><figcaption>${escapeHtml(photo.caption)}</figcaption></figure>`;
}

const ownHost = (href: string) => {
  try {
    const host = new URL(href, SITE).hostname;
    return host === "ai-tech-express.jp" || host.endsWith(".ai-tech-express.jp");
  } catch {
    return true;
  }
};

/** 本文中で残してよいリンクか（http(s) の外部サイトで、広告でないもの） */
export type LinkFilter = (href: string) => boolean;

const LINK = /<a\s[^>]*?href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
const BLOCK = /<(p|li|td|th|h2|h3|h4|blockquote|figcaption|dd|dt)(\s[^>]*)?>([\s\S]*?)<\/\1>/gi;

/**
 * 記事本文（描画済みの HTML）を SmartFormat 向けに整える。
 * isAd は広告・アフィリエイトのリンクか（文字だけ残す）。
 */
export function smartnewsBody(html: string, isAd: LinkFilter): string {
  let out = html
    // 相対 URL は絶対 URL に
    .replace(/(href|src)="\/(?!\/)/g, `$1="${SITE}/`)
    // スクリプト・フォーム・ボタン類（記事には無いはずだが、念のため）
    .replace(/<(script|style|noscript|form|button|iframe|object|embed)\b[\s\S]*?<\/\1>/gi, "")
    .replace(/<(input|button|iframe|embed)\b[^>]*\/?>/gi, "")
    // 配信先では不要な属性
    .replace(/\s(?:id|class|style|target|align|rel|loading|decoding|data-[\w-]+)="[^"]*"/g, "")
    // 見出しの h1 は記事の題名と重なるので h2 に
    .replace(/<h1(\s[^>]*)?>/gi, "<h2>")
    .replace(/<\/h1>/gi, "</h2>");

  const keep = (href: string) => {
    const plain = href.replace(/&amp;/g, "&");
    return /^https?:\/\//.test(plain) && !ownHost(plain) && !isAd(plain);
  };
  // 写真の注記の中のリンク（「公式発表」）は文字だけ（リンクの本数を本文の説明に回す）
  out = out.replace(/<figure>[\s\S]*?<\/figure>/gi, (fig) => fig.replace(LINK, (_w, _h, text: string) => text));
  // 段落ごとに外部リンクは1本まで・本文全体で BODY_LINK_LIMIT 本まで。ほかは文字だけ残す
  let used = 0;
  const marked = out.replace(BLOCK, (whole, tag: string, attrs: string | undefined, inner: string) => {
    let inBlock = 0;
    const next = inner.replace(LINK, (link: string, href: string, text: string) => {
      if (!keep(href) || inBlock >= 1 || used >= BODY_LINK_LIMIT) return text;
      inBlock += 1;
      used += 1;
      return `<a href="${href}">${text}</a>`.replace("<a ", "<a data-keep ");
    });
    return `<${tag}${attrs ?? ""}>${next}</${tag}>`;
  });
  // 段落の外に残ったリンク・印の付いていないリンクは文字だけ
  return marked
    .replace(/<a\s(?![^>]*data-keep)[^>]*>([\s\S]*?)<\/a>/gi, "$1")
    .replace(/<a data-keep /g, "<a ");
}

/** 本文の HTML にあるリンクの本数（テスト・確認用） */
export function countLinks(html: string): number {
  return (html.match(/<a\s/gi) ?? []).length;
}
