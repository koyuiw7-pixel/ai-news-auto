import { wordmark } from "@/lib/wordmark";

export const dynamic = "force-static";

/** スマートニュースの snf:darkModeLogo（ダークモードの SmartView 用）。透明の地に白と明るい赤の文字 */
export function GET() {
  return wordmark(410, 100, { background: "transparent", ink: "#ffffff", accent: "#ff6b5e" });
}
