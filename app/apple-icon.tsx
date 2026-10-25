import fs from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";
export const dynamic = "force-static";

/** iPhone のホーム画面に追加したときのアイコン（角丸は端末側で付く） */
export default async function AppleIcon() {
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
          borderRadius: 0,
          position: "relative",
        }}
      >
        <span style={{ fontFamily: "Dela", fontSize: 126, color: "#ffffff", lineHeight: 1, marginTop: -8 }}>サ</span>
        <span
          style={{
            position: "absolute",
            right: 14,
            top: 14,
            width: 26,
            height: 26,
            borderRadius: 13,
            background: "#d92d20",
          }}
        />
      </div>
    ),
    { ...size, fonts: [{ name: "Dela", data: font, weight: 400, style: "normal" }] },
  );
}
