import fs from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

/**
 * 横長のロゴ画像（白地に「サイソク」＋赤の「ニュース」）。ニュースアプリのフィードが求める大きさで作る。
 * 使うルートは force-static にして、ビルド時に一度だけ描く（Workers ではフォントを fs で読めないため）
 */
export type WordmarkTone = {
  /** 地の色（transparent で透明。スマートニュースのロゴは透明の PNG を推奨） */
  background: string;
  /** 「サイソク」の文字の色 */
  ink: string;
  /** 「ニュース」の文字の色 */
  accent: string;
};

export const WORDMARK_LIGHT: WordmarkTone = { background: "#ffffff", ink: "#111111", accent: "#d92d20" };

export async function wordmark(width: number, height: number, tone: WordmarkTone = WORDMARK_LIGHT): Promise<ImageResponse> {
  const font = await fs.readFile(path.join(process.cwd(), "assets", "fonts", "DelaGothicOne-Regular.ttf"));
  const size = Math.round(height * 0.6);
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: tone.background }}>
        <span style={{ fontFamily: "Dela", fontSize: size, color: tone.ink, letterSpacing: -1 }}>サイソク</span>
        <span style={{ fontFamily: "Dela", fontSize: Math.round(size * 0.6), color: tone.accent, marginLeft: Math.round(size * 0.2) }}>ニュース</span>
      </div>
    ),
    { width, height, fonts: [{ name: "Dela", data: font, weight: 400, style: "normal" }] },
  );
}
