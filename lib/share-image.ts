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
/** Google Discover の大きなカードに要る幅 */
export const DISCOVER_MIN_WIDTH = 1200;

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
/** 公式の写真の幅が分かっていて 1,200px 未満か（Discover の大きなカードに足りない。scripts/images.py が imageCredit.width に記録） */
export function smallOfficialPhoto(article: ShareImageInput): boolean {
  const width = article.imageCredit?.width ?? 0;
  return hasOfficialPhoto(article) && width > 0 && width < DISCOVER_MIN_WIDTH;
}

export function photoCover(article: ShareImageInput): string | null {
  // 公式の写真が 1,200px 以上ならそれが先。1,200px 未満なら表紙の写真のイメージ（あれば）を先にする（2026-11-10）
  if (article.noPhoto || (hasOfficialPhoto(article) && !smallOfficialPhoto(article))) return null;
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

/**
 * og:image の並び。cover は見出し入りのカバーの URL（無ければ空）。
 * 2026-11-11 読者目線レビュー 13位: X・Threads・LINE・Facebook は og:image の1枚目（X は twitter:image）を出す。
 * 写真を1枚目にしていた記事（年金・児童手当・出産手当金など、よく読まれている記事）は、共有したときに見出しの無い写真だけが出ていた。
 * 表紙の写真のイメージ（AI の写真）しか無い記事は、オーナーが選んだ見出し入りの「報道テロップ型」（/cover）を1枚目にし、写真は2枚目に残す。
 * 幅 1,200px 以上の公式の写真がある記事は、今までどおり写真が先（台帳 W32）。X のカード（twitter:image）は全記事で見出し入りのカバー（twitterImage）。
 * Google Discover の大きな写真（2026-11-10 の変更）は NewsArticle の image（articleImageOrder）で写真を先にしたまま
 */
export function shareImages(article: ShareImageInput, cover: string | undefined, alt: string): ShareImage[] {
  const card: ShareImage[] = cover ? [{ url: cover, width: 1200, height: 630, alt }] : [];
  // 公式の写真が無く、表紙の写真のイメージがある記事は、その写真（札だけ・見出しの文字なし）を先に。見出し入りのカバーは2つ目（2026-11-10）
  const photo = photoSharePath(article);
  // 本当の幅・高さを書く（公式の写真の約2割は元が 1,200px 未満。scripts/images.py が保存時に imageCredit に記録。SEO A15）
  const { width, height } = article.imageCredit ?? {};
  const official: ShareImage[] = hasOfficialPhoto(article)
    ? [{ url: article.thumbnail as string, ...(width && width > 0 ? { width, ...(height && height > 0 ? { height } : {}) } : { width: 1200 }), alt }]
    : [];
  const photoImage: ShareImage[] = photo ? [{ url: photo, width: PHOTO_SHARE_WIDTH, height: PHOTO_SHARE_HEIGHT, alt }] : [];
  // 幅 1,200px 以上の公式の写真は、今までどおり写真が先（台帳 W32・2026-11-04 オーナー承認。レビューの例はこの形ではない）
  if (official.length && !smallOfficialPhoto(article)) return [...official, ...card];
  if (card.length) return [...card, ...photoImage, ...official];
  if (photoImage.length || official.length) return [...photoImage, ...official];
  return article.thumbnail ? [{ url: article.thumbnail, width: 1280, height: 720 }] : [];
}

/** X のカード（twitter:image）。見出し入りのカバーがあれば全記事でそれ（2026-11-11 読者目線レビュー 13位）。無ければ og:image の1枚目 */
export function twitterImage(article: ShareImageInput, cover: string | undefined, alt: string): string | undefined {
  return cover || shareImages(article, cover, alt)[0]?.url;
}

/** NewsArticle の image の並び（og:image と同じ考え方）。サイトの中の絶対パスはそのまま返す（呼ぶ側でサイトの URL を付ける） */
export function articleImageOrder(article: ShareImageInput, cover: string): string[] {
  const photo = photoSharePath(article);
  const thumb = article.thumbnail ?? "";
  const list = photo
    ? [photo, cover, ...(hasOfficialPhoto(article) ? [thumb] : [])]
    : smallOfficialPhoto(article)
      ? [cover, thumb]
      : isOwnImage(thumb)
        ? [thumb, cover]
        : [cover, thumb];
  return list.filter(Boolean);
}
