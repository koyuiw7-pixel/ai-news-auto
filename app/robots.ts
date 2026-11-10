import type { MetadataRoute } from "next";
import { siteConfig } from "@/site.config";

export const dynamic = "force-static";

/**
 * 検索エンジンに加え、AI検索（ChatGPT・Claude・Perplexity・Gemini など）のクローラーも明示的に許可する。
 * AIの回答に引用されること（AEO・LLMO）も流入経路として狙うため。
 *
 * SEARCH_AGENTS: AIの検索・回答のために読みに来る巡回。オーナーの指示で、いつでも許可する（止めると引用が消える）。
 *   tests/test_robots_ai_access.cjs と scripts/llmo_access_check.py（毎日の本番確認）が、止めていないかを見張る。
 * TRAINING_CRAWLERS: AIの学習用の巡回。許すかどうかはオーナーが決める（オーナー判断 B1）。決まるまでは今と同じく許可のまま。
 */
const SEARCH_AGENTS = [
  "OAI-SearchBot",
  "ChatGPT-User",
  "PerplexityBot",
  "Perplexity-User",
  "Claude-SearchBot",
  "Claude-User",
  "Bingbot",
  "DuckAssistBot",
  "MistralAI-User",
  "MistralAI-Index",
];

const TRAINING_CRAWLERS = [
  "GPTBot",
  "ClaudeBot",
  "Google-Extended",
  "Applebot-Extended",
  "MistralAI-Training",
];

const BLOCKED_PATHS = ["/api/", "/review"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: BLOCKED_PATHS },
      { userAgent: SEARCH_AGENTS, allow: "/", disallow: BLOCKED_PATHS },
      { userAgent: TRAINING_CRAWLERS, allow: "/", disallow: BLOCKED_PATHS },
    ],
    sitemap: [`${siteConfig.url}/sitemap.xml`, `${siteConfig.url}/news-sitemap.xml`],
    host: siteConfig.url,
  };
}
