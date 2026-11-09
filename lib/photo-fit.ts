import type { ArticlePhoto } from "@/lib/articles";

/**
 * 写真を 16:9 の枠に切り抜かずに収めるか（2026-11-10 オーナー「画像が見切れている記事があるのはダサい」）。
 * 文字の多いバナー・図（fit: "contain"）と、縦長・正方形・極端に横長の写真は、切り抜くと主役や文字が欠けるので枠に丸ごと収める。
 * クライアントの部品からも読めるよう、依存のない小さなファイルにする
 */
export function containPhoto(photo: Pick<ArticlePhoto, "fit" | "ar"> | undefined | null): boolean {
  if (!photo) return false;
  if (photo.fit === "contain") return true;
  return typeof photo.ar === "number" && (photo.ar < 1.4 || photo.ar > 2.4);
}
