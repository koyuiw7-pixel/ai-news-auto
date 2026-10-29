import fs from "node:fs/promises";
import path from "node:path";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";
export const dynamic = "force-static";

/** iPhone のホーム画面に追加したときのアイコン（角丸は端末側で付く）。赤地に白の「速」のブランドアイコン */
export default async function AppleIcon() {
  const png = await fs.readFile(path.join(process.cwd(), "public", "icons", "apple-icon-180.png"));
  return new Response(new Uint8Array(png), { headers: { "Content-Type": contentType } });
}
