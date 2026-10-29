import fs from "node:fs/promises";
import path from "node:path";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";
export const dynamic = "force-static";

/**
 * サイトのアイコン（ブラウザのタブ・検索結果の横に出る）。赤地に白の「速」＋「サイソク」のブランドアイコン。
 * 元画像は public/icons/ に置いたPNG（out/brand/saisoku-icon-2048.png から縮小）。
 * URL（/icon）はプッシュ通知の icon/badge や古い Service Worker も参照しているので、ファイル置き換えでなくこのルートで返す
 */
export default async function Icon() {
  const png = await fs.readFile(path.join(process.cwd(), "public", "icons", "icon-512.png"));
  return new Response(new Uint8Array(png), { headers: { "Content-Type": contentType } });
}
