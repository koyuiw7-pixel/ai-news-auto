// Bluesky の独自ドメインハンドル（HTTP 方式）。/.well-known/atproto-did から rewrite で来る
export const dynamic = "force-static";

export function GET() {
  return new Response("did:plc:nwiq4lvu5kt4jr2tomn6ui7k", {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
