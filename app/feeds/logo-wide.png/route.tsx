import { wordmark } from "@/lib/wordmark";

export const dynamic = "force-static";

/** スマートニュースの snf:logo 用（横700px以下・縦100px前後） */
export function GET() {
  return wordmark(600, 100);
}
