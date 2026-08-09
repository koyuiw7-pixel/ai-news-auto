import { apiJson, authorize, handleOptions } from "@/lib/api-auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const REPO = process.env.INTEGRATION_GITHUB_REPO ?? "koyuiw7-pixel/ai-news-auto";
const WORKFLOW = "auto_run.yml";

type GhRun = {
  id: number;
  status: string; // queued / in_progress / completed
  conclusion: string | null; // success / failure / cancelled
  created_at: string;
  updated_at: string;
  run_started_at: string;
  html_url: string;
  event: string;
};

/**
 * 記事生成ワークフローの実行状況。
 * サイト側は静的生成なので「いま動いているか」は GitHub に聞かないと分からない。
 * 連携先に GitHub の認証情報を渡さずに済むよう、ここでプロキシする。
 */
export async function GET(request: Request) {
  const auth = authorize(request);
  if (!auth.ok) return auth.response;

  const token = process.env.INTEGRATION_GITHUB_TOKEN;
  if (!token) {
    return apiJson(
      request,
      {
        error: "github_token_missing",
        message:
          "INTEGRATION_GITHUB_TOKEN が未設定です。Contents:Read / Actions:Read の Fine-grained PAT を設定してください。",
      },
      503,
    );
  }

  const limit = Math.min(
    Math.max(
      Number.parseInt(new URL(request.url).searchParams.get("limit") ?? "10", 10) || 10,
      1,
    ),
    30,
  );

  let response: Response;
  try {
    response = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=${limit}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        cache: "no-store",
      },
    );
  } catch (error) {
    return apiJson(
      request,
      { error: "github_unreachable", message: String(error) },
      502,
    );
  }

  if (!response.ok) {
    return apiJson(
      request,
      {
        error: "github_error",
        status: response.status,
        message: await response.text().catch(() => ""),
      },
      502,
    );
  }

  const data = (await response.json()) as { workflow_runs?: GhRun[] };
  const runs = data.workflow_runs ?? [];

  return apiJson(request, {
    schedule: "0 */3 * * * (UTC) — 3時間ごと",
    isRunning: runs.some((r) => r.status !== "completed"),
    lastSuccessAt:
      runs.find((r) => r.conclusion === "success")?.updated_at ?? null,
    consecutiveFailures: countLeadingFailures(runs),
    runs: runs.map((r) => ({
      id: r.id,
      status: r.status,
      conclusion: r.conclusion,
      trigger: r.event,
      startedAt: r.run_started_at,
      finishedAt: r.status === "completed" ? r.updated_at : null,
      durationSec:
        r.status === "completed"
          ? Math.round(
              (new Date(r.updated_at).getTime() -
                new Date(r.run_started_at).getTime()) /
                1000,
            )
          : null,
      url: r.html_url,
    })),
  });
}

/** 直近から数えて何回連続で失敗しているか（監視アラートの判定用） */
function countLeadingFailures(runs: GhRun[]): number {
  let count = 0;
  for (const run of runs) {
    if (run.status !== "completed") continue;
    if (run.conclusion === "success") break;
    count += 1;
  }
  return count;
}

export function OPTIONS(request: Request) {
  return handleOptions(request);
}
