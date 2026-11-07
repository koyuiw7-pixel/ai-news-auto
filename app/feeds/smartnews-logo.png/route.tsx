import { wordmark } from "@/lib/wordmark";

export const dynamic = "force-static";

/**
 * スマートニュースの snf:logo（SmartView の上に出るロゴ）。仕様の推奨は「横700px以下・縦およそ100px・透明のPNG・横長・余分な縁なし」。
 * 明るい地・暗い地のどちらでも読めるよう、文字は濃い色と赤（暗い地の分は snf:darkModeLogo で別に出す）
 */
export function GET() {
  return wordmark(410, 100, { background: "transparent", ink: "#111111", accent: "#d92d20" });
}
