import fs from "node:fs";
import path from "node:path";
import { apiJson, authorize, handleOptions } from "@/lib/api-auth";
import { getAllArticles, getAllChannels, getAllGenres } from "@/lib/articles";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type State = {
  processed?: Record<string, { at?: string; slug?: string; skipped?: boolean }>;
  failed?: Record<string, number>;
};

function readState(): State {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(process.cwd(), "content", "state.json"), "utf8"),
    );
  } catch {
    return {};
  }
}

function countSince(dates: (string | undefined)[], hours: number): number {
  const since = Date.now() - hours * 3600_000;
  return dates.filter((d) => d && new Date(d).getTime() >= since).length;
}

export function OPTIONS(request: Request) {
  return handleOptions(request);
}

export function GET(request: Request) {
  const auth = authorize(request);
  if (!auth.ok) return auth.response;

  const articles = getAllArticles();
  const state = readState();
  const processed = Object.values(state.processed ?? {});
  const generatedAt = articles.map((a) => a.generatedAt);

  return apiJson(request, {
    generatedAt: new Date().toISOString(),
    articles: {
      total: articles.length,
      last24h: countSince(generatedAt, 24),
      last7d: countSince(generatedAt, 24 * 7),
      last30d: countSince(generatedAt, 24 * 30),
      latestPublishedAt: articles[0]?.publishedAt ?? null,
      latestGeneratedAt:
        generatedAt.slice().sort().reverse()[0] ?? null,
    },
    byGenre: Object.fromEntries(
      getAllGenres().map((g) => [g.slug, { label: g.label, count: g.count }]),
    ),
    byChannel: Object.fromEntries(
      getAllChannels().map((c) => [c.slug, { label: c.label, count: c.count }]),
    ),
    pipeline: {
      // 解析を試みた動画の総数（記事化されなかったものを含む）
      videosProcessed: processed.length,
      // ジャンル外・情報量不足でスキップした本数
      videosSkipped: processed.filter((p) => p?.skipped).length,
      videosFailed: Object.keys(state.failed ?? {}).length,
    },
  });
}
