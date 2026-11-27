/**
 * 広告の「押した割合」の決まり（2026-11-27。オーナー: 人のクリック率 15% 以上が続いて、はじめて良い広告）。
 *   押した割合 = 広告を押した人 ÷ 広告の囲みを見た人（同じ日・同じ置き場所）
 *   見た = 囲み（data-aff-pos）が画面に半分以上入った状態が1秒続いた（components/AdSeenTracker.tsx → POST /api/aff/seen → cloudflare/aff.ts）
 *   押した = 今までどおり components/AffClickTracker.tsx → POST /api/aff/click。Do Not Track / GPC・?_internal=1 のブラウザのクリックは、
 *            クリック数には残すが、押した割合の分子には入れない（見た数と同じ人たちで比べる）
 * 人の数は「秘密の値 + 日付 + IP + UA」の短いハッシュ（日をまたいでたどれない）。日をまたいで足さない。
 */

export const AD_SEEN_MS = 1000;
export const AD_SEEN_RATIO = 0.5;

const PATH = /^\/[A-Za-z0-9\-._~%!$&'()*+,;=:@/]{0,200}$/;
const POS = /^[a-z0-9-]{1,32}$/;

export type AdSeenEvent = { path: string; pos: string; ab?: "a" | "b"; arm?: "1" | "2" };

/** 画面から送る中身（不正な値なら undefined で送らない）。クエリ文字列は送らない */
export function adSeenBody(input: { path: string; pos: string; ab?: string | null; arm?: string | null }): string | undefined {
  const event = parseAdSeen(input);
  return event ? JSON.stringify(event) : undefined;
}

/** 受け口で確かめる（cloudflare/aff.ts）。パス・置き場所の形、A/B は a|b と 1|2 だけ */
export function parseAdSeen(body: unknown): AdSeenEvent | undefined {
  if (!body || typeof body !== "object") return undefined;
  const b = body as Record<string, unknown>;
  const path = typeof b.path === "string" ? b.path : "";
  const pos = typeof b.pos === "string" ? b.pos : "";
  if (!PATH.test(path) || !POS.test(pos)) return undefined;
  if (b.ab !== undefined && b.ab !== null && b.ab !== "a" && b.ab !== "b") return undefined;
  if (b.arm !== undefined && b.arm !== null && b.arm !== "1" && b.arm !== "2") return undefined;
  return { path, pos, ...(b.ab === "a" || b.ab === "b" ? { ab: b.ab } : {}), ...(b.arm === "1" || b.arm === "2" ? { arm: b.arm } : {}) };
}

/** 置き場所から枠の中の順番を外す（「tool-result-1」→「tool-result」。cloudflare/aff.ts の byPlacement と同じ） */
export const posGroup = (pos: string | undefined) => (pos ?? "other").replace(/-\d+$/, "");

type Seen = { path?: string; pos?: string; ab?: string; arm?: string; v?: string };
type Click = { path?: string; pos?: string; ab?: string; arm?: string; v?: string; q?: number };

export type RateRow = { seen: number; clicks: number; clickers: number; seenClickers: number; rate: number | null };

/**
 * 見た人と押した人の表。行ごとに
 *   seen = 見た人（日内の推定人数）、clicks = 押した回数（割合に入れるクリックだけ）、clickers = 押した人、
 *   seenClickers = 押した人のうち同じ行で見た記録もある人、rate = clickers ÷ seen（見た人がいなければ null）
 */
export function adRateTable(seen: Seen[], clicks: Click[]) {
  type Acc = { seen: Set<string>; clicks: number; clickers: Set<string> };
  const tables = { pos: new Map<string, Acc>(), variant: new Map<string, Acc>(), arm: new Map<string, Acc>(), tool: new Map<string, Acc>() };
  const acc = (map: Map<string, Acc>, key: string) => {
    const row = map.get(key) ?? { seen: new Set<string>(), clicks: 0, clickers: new Set<string>() };
    map.set(key, row);
    return row;
  };
  const keysOf = (row: Seen) => {
    const pos = posGroup(row.pos);
    const keys: [keyof typeof tables, string][] = [["pos", pos]];
    if (row.ab) keys.push(["variant", `${pos}|${row.ab}`]);
    if (row.arm) keys.push(["arm", `${pos}|${row.arm}`]);
    if (row.path?.startsWith("/tools/")) keys.push(["tool", `${row.path}|${pos}|${row.ab ?? ""}`]);
    return keys;
  };
  const total = { seen: new Set<string>(), clicks: 0, clickers: new Set<string>() };
  for (const row of seen) {
    const v = row.v ?? "";
    if (!v) continue;
    total.seen.add(v);
    for (const [table, key] of keysOf(row)) acc(tables[table], key).seen.add(v);
  }
  for (const row of clicks) {
    if (row.q) continue;
    const v = row.v ?? "";
    total.clicks++;
    if (v) total.clickers.add(v);
    for (const [table, key] of keysOf(row)) {
      const r = acc(tables[table], key);
      r.clicks++;
      if (v) r.clickers.add(v);
    }
  }
  const out = (row: Acc): RateRow => ({
    seen: row.seen.size,
    clicks: row.clicks,
    clickers: row.clickers.size,
    seenClickers: [...row.clickers].filter((v) => row.seen.has(v)).length,
    rate: row.seen.size ? row.clickers.size / row.seen.size : null,
  });
  const list = <T extends Record<string, string>>(map: Map<string, Acc>, split: (key: string) => T) =>
    [...map].map(([key, row]) => ({ ...split(key), ...out(row) })).sort((a, b) => b.seen - a.seen || b.clicks - a.clicks);
  return {
    total: out(total),
    byPos: list(tables.pos, (key) => ({ pos: key })),
    byVariant: list(tables.variant, (key) => { const [pos, ab] = key.split("|"); return { pos, ab }; }),
    byArm: list(tables.arm, (key) => { const [pos, arm] = key.split("|"); return { pos, arm }; }),
    byToolPath: list(tables.tool, (key) => { const [path, pos, ab] = key.split("|"); return { path, pos, ab }; }),
  };
}

/** 後から描いた広告の枠（components/ToolAdSlot.tsx）を、見た数の計測（components/AdSeenTracker.tsx）にすぐ知らせる合図 */
export const AD_SLOT_EVENT = "saisoku:ad-slot";
