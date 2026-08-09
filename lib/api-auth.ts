import { timingSafeEqual } from "node:crypto";

/**
 * 外部システム連携APIの認証。
 *
 * INTEGRATION_API_TOKEN が未設定のときは API 自体を無効にする（503）。
 * 「トークン未設定なら誰でも読める」状態を絶対に作らないため。
 */

export type AuthResult = { ok: true } | { ok: false; response: Response };

const JSON_HEADERS = { "Content-Type": "application/json; charset=utf-8" };

function json(body: unknown, status: number, extra?: HeadersInit): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...JSON_HEADERS, ...extra },
  });
}

/** 文字列長の違いから内容を推測されないよう、長さもタイミング安全に比較する */
function safeEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  if (bufA.length !== bufB.length) {
    // 長さが違っても同じだけ時間を使う
    timingSafeEqual(bufA, bufA);
    return false;
  }
  return timingSafeEqual(bufA, bufB);
}

export function authorize(request: Request): AuthResult {
  const expected = process.env.INTEGRATION_API_TOKEN;

  if (!expected) {
    return {
      ok: false,
      response: json(
        {
          error: "integration_api_disabled",
          message:
            "INTEGRATION_API_TOKEN が未設定のため、この API は無効です。",
        },
        503,
      ),
    };
  }

  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";

  if (!token || !safeEqual(token, expected)) {
    return {
      ok: false,
      response: json(
        { error: "unauthorized", message: "有効な Bearer トークンが必要です。" },
        401,
        { "WWW-Authenticate": 'Bearer realm="integration"' },
      ),
    };
  }

  return { ok: true };
}

/** 連携先オリジンのみ許可。未設定ならCORSヘッダを付けない（same-origin のみ） */
export function corsHeaders(request: Request): HeadersInit {
  const allowed = (process.env.INTEGRATION_ALLOWED_ORIGINS ?? "")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean);
  const origin = request.headers.get("origin");

  if (!origin || !allowed.includes(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    Vary: "Origin",
  };
}

export function apiJson(
  request: Request,
  body: unknown,
  status = 200,
): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      ...JSON_HEADERS,
      "Cache-Control": "no-store",
      ...corsHeaders(request),
    },
  });
}

export function handleOptions(request: Request): Response {
  return new Response(null, { status: 204, headers: corsHeaders(request) });
}
