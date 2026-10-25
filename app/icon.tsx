import fs from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";
export const dynamic = "force-static";

/** サイトのアイコン（ブラウザのタブ・検索結果の横に出る）。黒地に白の「サ」と、速報の赤い点 */
export default async function Icon() {
  const font = await fs.readFile(path.join(process.cwd(), "assets", "fonts", "DelaGothicOne-Regular.ttf"));
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#111111",
          borderRadius: 112,
          position: "relative",
        }}
      >
        <span style={{ fontFamily: "Dela", fontSize: 360, color: "#ffffff", lineHeight: 1, marginTop: -24 }}>サ</span>
        <span
          style={{
            position: "absolute",
            right: 46,
            top: 46,
            width: 72,
            height: 72,
            borderRadius: 36,
            background: "#d92d20",
          }}
        />
      </div>
    ),
    { ...size, fonts: [{ name: "Dela", data: font, weight: 400, style: "normal" }] },
  );
}
