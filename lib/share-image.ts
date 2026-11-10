/**
 * 記事のシェア画像（og:image・X のカード）の順番（2026-11-04 オーナー承認のピボット・台帳 W32）。
 *
 * Google Discover（スマホの Google アプリのおすすめ欄）は、幅 1,200px 以上の大きな写真と
 * robots の max-image-preview:large がある記事を大きなカードで出す。Google は「ロゴや文字の多い画像は避ける」と案内している。
 * これまでは公式の写真がある記事でも、見出しの文字入りのカバー（/cover。1200×630）を先に出していた。
 *
 * - 公式発表の写真（scripts/images.py が縮小してサイトで配信する /img/<名前>.jpg。幅 1,200px）がある記事は、その写真を先に出す
 * - 公式の写真が無い記事（AI の絵・フリー素材・外部の画像）は、これまでどおり見出し入りのカバーが先
 * - カバーは2つ目に残す（題名は1つだけ。カバーの題名も記事の題名から作る＝台帳 A29）
 */
import { titleHash } from "./cover-path";
import { isOwnImage } from "./thumb-url";

type ShareImageInput = {
  slug?: string;
  thumbnail?: string;
  imageCredit?: { kind?: string; imageKind?: string; width?: number; height?: number } | null;
  coverImage?: string | null;
  coverCredit?: { kind?: string; model?: string; width?: number; height?: number } | null;
  noPhoto?: boolean | null;
};

/** 写真の共有画像（/cover/<slug>/photo）の大きさ。Google Discover の大きなカード向けに 16:9・幅 1,200px */
export const PHOTO_SHARE_WIDTH = 1200;
export const PHOTO_SHARE_HEIGHT = 675;
/** 写真の共有画像の版。描き方を変えたら1つ上げる（URL の ?v= が変わり、古い画像のキャッシュを使わせない） */
export const PHOTO_SHARE_VERSION = 2;

export type ShareImage = { url: string; width?: number; height?: number; alt?: string };

/** 公式発表の写真をシェア画像の先頭にしてよいか（サイトで配信する幅 1,200px の写真で、出典が公式発表） */
export function hasOfficialPhoto(article: ShareImageInput): boolean {
  if (!isOwnImage(article.thumbnail) || article.imageCredit?.kind !== "official") return false;
  // 2026-11-09（台帳 S49）: 公式のロゴ・サイト共通の画像、ほかの記事のために保存した画像は先頭にしない（見出し入りのカバーが先）
  if (["logo", "generic"].includes(article.imageCredit?.imageKind ?? "")) return false;
  const name = /\/img\/([^/?#]+)$/.exec((article.thumbnail ?? "").split("?")[0])?.[1] ?? "";
  return !article.slug || name.startsWith(article.slug.slice(0, 120));
}

/**
 * 表紙の写真（2026-11-10 Discover の準備）。公式の写真が無い記事で、記事ページの表紙に出している写真のイメージ
 * （coverImage。Muse の写真・Workers AI の表紙。どちらも記事に合うかを確かめたもの。lib/noir.ts の noirCover と同じ順）。
 * 文字の多い図の表紙・見出し入りのカバーより先に、共有画像（og:image）と NewsArticle の image に出す。無ければ null
 */
export function photoCover(article: ShareImageInput): string | null {
  if (article.noPhoto || hasOfficialPhoto(article)) return null;
  const cover = (article.coverImage ?? "").trim();
  if (!cover || article.coverCredit?.kind !== "ai" || !isOwnImage(cover)) return null;
  return cover;
}

/** 表紙の写真の共有画像の URL（写真の下に「画像はイメージ（AI生成）」の札だけを付けた 1200×675。app/cover/[slug]/photo/route.tsx） */
export function photoSharePath(article: ShareImageInput): string | null {
  const cover = photoCover(article);
  if (!cover || !article.slug) return null;
  return `/cover/${article.slug}/photo?v=${PHOTO_SHARE_VERSION}-${titleHash(cover)}`;
}

/** og:image の並び。cover は見出し入りのカバーの URL（無ければ空） */
export function shareImages(article: ShareImageInput, cover: string | undefined, alt: string): ShareImage[] {
  const card: ShareImage[] = cover ? [{ url: cover, width: 1200, height: 630, alt }] : [];
  // 公式の写真が無く、表紙の写真のイメージがある記事は、その写真（札だけ・見出しの文字なし）を先に。見出し入りのカバーは2つ目（2026-11-10）
  const photo = photoSharePath(article);
  if (photo) return [{ url: photo, width: PHOTO_SHARE_WIDTH, height: PHOTO_SHARE_HEIGHT, alt }, ...card];
  if (hasOfficialPhoto(article)) {
    // 本当の幅・高さを書く（公式の写真の約2割は元が 1,200px 未満。scripts/images.py が保存時に imageCredit に記録。SEO A15）
    const { width, height } = article.imageCredit ?? {};
    const size = width && width > 0 ? { width, ...(height && height > 0 ? { height } : {}) } : { width: 1200 };
    return [{ url: article.thumbnail as string, ...size, alt }, ...card];
  }
  if (card.length) return card;
  return article.thumbnail ? [{ url: article.thumbnail, width: 1280, height: 720 }] : [];
}
