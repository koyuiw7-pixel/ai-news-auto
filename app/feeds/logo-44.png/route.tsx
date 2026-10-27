import { wordmark } from "@/lib/wordmark";

export const dynamic = "force-static";

/** グノシーの gnf:wide_image_link 用（縦44px必須・横100〜550px） */
export function GET() {
  return wordmark(300, 44);
}
