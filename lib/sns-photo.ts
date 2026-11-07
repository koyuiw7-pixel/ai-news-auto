import firms from "./research-firms.json";
import type { ImageCredit } from "./articles";
import type { BodyImage } from "./body-images";

/**
 * SNS の投稿の画像（/card/<slug>。Threads・Bluesky・X・Facebook が同じカードを使う）に、どの写真を敷くか。
 * 2026-11-07 オーナー承認（台帳 S45）: 会社の公式発表の写真を、出典（画像：会社名（公式発表より））つきで使う。
 *
 * 1. 記事の写真（thumbnail）が公式発表の写真で、文字が主役でないもの（写真・報道用素材・公式動画のコマ・キービジュアル）→ そのまま
 * 2. 1 でなければ、本文に置いた公式の写真（bodyImages の photo / kit）→ それをカードに敷き、出典もその会社にする
 * 3. どちらも無ければ今までのカード（AI のイメージなら「画像はイメージ（AI生成）」のまま）
 *
 * 使わないもの: 調査会社・情報会社のサイトの画像（台帳 A37。lib/research-firms.json）、告知のバナー・図・ロゴ、
 * 表紙の判定で大きな文字があるとされた写真（heroOk: false）。公式の動画は再投稿しない（静止画のコマだけ。カードの写真として使う）。
 * Python 側の同じ判定は scripts/sns_rules.py の sns_photo（門番・下見で使う）。ずれは tests/test_sns_official_photo.cjs と
 * tests/test_sns_official_photo_20261107.py が同じ例で確かめる。
 */

/** 記事の写真として SNS に出してよい公式の画像の種類（imageKind。無ければ写真） */
export const HERO_SNS_KINDS = ["photo", "kit", "video", "youtube", "hero"];
/** 本文の公式の画像のうち、カードに敷いてよい種類（図・キービジュアルは文字が多いので使わない） */
export const BODY_SNS_KINDS = ["photo", "kit"];
const OUR_IMAGE = /^https:\/\/ai-tech-express\.jp\/img\/[\w.-]+\.(?:jpg|jpeg|png|webp)$/;

type Photoable = {
  slug?: string;
  thumbnail: string;
  imageCredit?: ImageCredit;
  heroOk?: boolean;
  bodyImages?: BodyImage[];
  channelSlug?: string;
  sourceUrl?: string;
  imageFocus?: { x?: number; y?: number; box: [number, number, number, number]; ar: number; src: string };
};

export type SnsPhoto = { src: string; credit: ImageCredit; from: "thumbnail" | "body" };

const FIRM_HOSTS: Record<string, string> = (firms as { hosts?: Record<string, string> }).hosts ?? {};
const FIRM_CHANNELS: Record<string, string> = (firms as { channels?: Record<string, string> }).channels ?? {};

function hostOf(url?: string): string {
  try {
    return new URL(url ?? "").hostname.toLowerCase();
  } catch {
    return "";
  }
}

/** URL が調査会社・情報会社のサイトか */
export function researchFirmUrl(url?: string): boolean {
  const host = hostOf(url);
  return Boolean(host) && Object.keys(FIRM_HOSTS).some((h) => host === h || host.endsWith(`.${h}`));
}

/** 記事が調査会社・情報会社の記事か（発信元か元記事の URL） */
export function researchFirmArticle(article: Pick<Photoable, "channelSlug" | "sourceUrl">): boolean {
  return Object.prototype.hasOwnProperty.call(FIRM_CHANNELS, (article.channelSlug ?? "").trim()) || researchFirmUrl(article.sourceUrl);
}

/** 記事の写真（thumbnail）を公式の写真として SNS に出してよいか */
function heroQualifies(article: Photoable): boolean {
  const c = article.imageCredit;
  if (c?.kind !== "official" || !(c.org || c.via || c.provider)) return false;
  if (article.heroOk === false) return false;
  if (!HERO_SNS_KINDS.includes(c.imageKind ?? "photo")) return false;
  return !researchFirmUrl(c.sourceUrl) && !researchFirmUrl((c as { original?: string }).original);
}

function bodyQualifies(im: BodyImage): boolean {
  if (!im || !OUR_IMAGE.test(im.src ?? "") || !(im.credit ?? "").trim()) return false;
  if (!BODY_SNS_KINDS.includes(im.kind ?? "")) return false;
  return !researchFirmUrl(im.sourceUrl) && !researchFirmUrl(im.original);
}

/** SNS のカードに敷く公式の写真（無ければ null ＝ 今までのカード） */
export function snsPhoto(article: Photoable): SnsPhoto | null {
  if (researchFirmArticle(article)) return null;
  if (article.thumbnail && heroQualifies(article)) return { src: article.thumbnail, credit: article.imageCredit as ImageCredit, from: "thumbnail" };
  const body = (article.bodyImages ?? []).find(bodyQualifies);
  if (!body) return null;
  return {
    src: body.src,
    credit: { kind: "official", org: body.credit.trim(), sourceUrl: body.sourceUrl, width: body.width, height: body.height, ...(body.kind === "kit" ? { imageKind: "kit" } : {}) },
    from: "body",
  };
}

/**
 * カードを描くときの記事（本文の公式の写真を使うときだけ、写真・出典・主役の枠を差し替える。それ以外はそのまま）。
 * 出典を差し替えるので、公式の写真に「AI生成」の注記が付くことはない（逆に AI の画像を公式とは書かない）
 */
export function snsCardArticle<T extends Photoable>(article: T): T {
  const photo = snsPhoto(article);
  if (!photo || photo.from === "thumbnail") return article;
  const ar = photo.credit.width && photo.credit.height ? photo.credit.width / photo.credit.height : undefined;
  return {
    ...article,
    thumbnail: photo.src,
    imageCredit: photo.credit,
    // 主役の枠は元の写真のもの。差し替えた写真では写真全体を主役とみなす（切らない側）
    imageFocus: ar ? { x: 0.5, y: 0.5, box: [0, 0, 1, 1], ar, src: photo.src } : undefined,
  } as T;
}

type Coverable = Photoable & { coverImage?: string; coverCredit?: ImageCredit; noPhoto?: boolean };

/** 記事の写真（thumbnail）を共有の画像にそのまま使ってよいか（空・AI の絵・写真なしの印 card は使わない） */
function thumbnailUsable(article: Coverable): boolean {
  const kind = article.imageCredit?.kind;
  return Boolean(article.thumbnail) && kind !== "ai" && kind !== "card";
}

/**
 * 共有の画像（og:image の /cover/<slug> と SNS の /card/<slug>）に敷く写真を決めた記事（2026-11-07 オーナー指摘）。
 * 不二家の値上げの記事で、記事の写真が無い（thumbnail ""）のに表紙用の AI のイメージ（coverImage）があったのに、
 * カバーもカードも thumbnail だけを見ていたので、暗い・青い文字だけの画像が X とリンクカードに出た。
 * 順: ①使える記事の写真（今までどおり） ②表紙用の AI のイメージ（coverImage。scripts/noir_cover.py が話題とのつながりを確かめたもの。
 * 出典を coverCredit に差し替えるので「画像はイメージ（AI生成）」の札が付く） ③どちらも無ければ今までの文字のカード。
 * 地震・津波の記事（noPhoto）は写真を付けない。force: 記事の写真が取得できなかったときに②へ回す
 */
export function shareImageArticle<T extends Coverable>(article: T, force = false): T {
  if (article.noPhoto) return article;
  const cover = article.coverImage && article.coverCredit?.kind === "ai" ? article.coverImage : "";
  if (!cover || cover === article.thumbnail) return article;
  if (!force && thumbnailUsable(article)) return article;
  return { ...article, thumbnail: cover, imageCredit: article.coverCredit, heroOk: undefined, imageFocus: undefined } as T;
}
