import fs from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

export const dynamic = "force-static";

/** 構造化データ（publisher.logo）用のロゴ画像。600x60 は Google の推奨サイズ */
export async function GET() {
  const font = await fs.readFile(path.join(process.cwd(), "assets", "fonts", "DelaGothicOne-Regular.ttf"));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", background: "#ffffff", paddingLeft: 8 }}>
        <span style={{ fontFamily: "Dela", fontSize: 46, color: "#111111", letterSpacing: -1 }}>サイソク</span>
      </div>
    ),
    { width: 600, height: 60, fonts: [{ name: "Dela", data: font, weight: 400, style: "normal" }] },
  );
}
