/**
 * 記事を「どこまで読んだか・どれだけ見ていたか・次にどこを押したか」の自前計測の決まり
 * （画面 components/ReadingBeacon.tsx と Worker cloudflare/reading.ts が共有する。集計は scripts/reading_report.py）。
 * 2026-11-10: 流入が増えても1訪問あたり約1.04ページで、広告も押されない。原因（見づらい・長い・次の記事が遠い・広告が見られていない）を
 * 推測でなく数字で確かめるために足した。見た目は変えない。
 *
 * 送るのは 1ページの表示につき1回だけ（ページを離れる・タブを隠す・サイト内で次のページへ移るとき）:
 *   p 記事の slug / s 流入元（外から来た入口なら lib/inflow.ts の分類、サイト内の移動なら "internal"）
 *   d 読んだ深さ（記事ページのフッターより上を 100 とした割合。10 刻み） / t 画面に出ていた秒数（区切りに丸める）
 *   n 「次に読む記事」の欄が画面に出たか / a 画面に半分以上出た PR 枠（data-aff-pos）の一覧 / x 最後に押したサイト内リンクの場所
 * Cookie・識別子・参照元の原文・クエリ全体・押したリンク先の URL は送らない。
 */
import { INFLOW_SOURCES, validPageKey, type InflowSource } from "./inflow";

export const READING_SOURCES = [...INFLOW_SOURCES, "internal"] as const;
export type ReadingSource = InflowSource | "internal";

/** 秒数の区切り（その値以上・次の値未満を左端に丸める）。最後は 600 秒以上 */
export const TIME_BUCKETS = [0, 5, 10, 20, 30, 60, 120, 180, 300, 600] as const;
export const MAX_DEPTH = 100;

/** サイト内リンクを押した場所。header（上のメニュー・速報の帯）/ story（要点の下の「この話の続き」）/ money（要点の下の「自分は対象か確かめる」。data-money-link）/ nextread（次に読む記事）/ aside（横の欄・よく読まれている記事）/ footer / body（本文とその前後） */
export const EXIT_ZONES = ["", "header", "story", "money", "body", "nextread", "aside", "footer"] as const;
export type ExitZone = typeof EXIT_ZONES[number];

const AD_POS = /^[a-z][a-z0-9-]{0,31}$/;
export const MAX_AD_POS = 8;

export const timeBucket = (seconds: number): number => {
  const s = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
  let out = 0;
  for (const edge of TIME_BUCKETS) if (s >= edge) out = edge;
  return out;
};

export const depthBucket = (ratio: number): number => {
  const r = Number.isFinite(ratio) ? Math.min(Math.max(ratio, 0), 1) : 0;
  // 端数を切り捨てるが、最後の 3% はフッター手前の余白なので読み切りとみなす
  return r >= 0.97 ? MAX_DEPTH : Math.floor(r * 10) * 10;
};

/** PR 枠の名前（data-aff-pos）。末尾の番号（action-ad-1 など）は外し、重複を除いて最大 8 個 */
export function normalizeAdPositions(list: string[]): string[] {
  const out: string[] = [];
  for (const raw of list) {
    const pos = raw.replace(/-\d+$/, "");
    if (AD_POS.test(pos) && !out.includes(pos)) out.push(pos);
    if (out.length >= MAX_AD_POS) break;
  }
  return out;
}

/** 得のカードの A/B の arm（lib/ad-ab.ts。台帳 W41） */
export const AB_ARMS = ["1", "2"] as const;
export type ReadingArm = typeof AB_ARMS[number];

/**
 * b: 得のカードの A/B の arm（<html data-abc>）/ k: 画面に半分以上出た、A/B のカードのある PR 枠（data-aff-pos）。表示の数（クリック率の分母）に使う。
 * どちらも省略できる（A/B のカードを見ていない表示・古い画面）
 */
export type ReadingEvent = { p: string; s: ReadingSource; d: number; t: number; n: boolean; a: string[]; x: ExitZone; b?: ReadingArm; k?: string[] };

/** 受け取った送信の中身を確かめて、決まった形に直す。おかしければ null */
export function parseReading(body: Record<string, unknown> | null): ReadingEvent | null {
  if (!body) return null;
  const { p, s, d, t, n, a, x, b, k } = body;
  if (typeof p !== "string" || !validPageKey(p) || p === "_home" || p.startsWith("digest-")) return null;
  if (typeof s !== "string" || !READING_SOURCES.includes(s as ReadingSource)) return null;
  if (typeof d !== "number" || !Number.isInteger(d) || d < 0 || d > MAX_DEPTH || d % 10 !== 0) return null;
  if (typeof t !== "number" || !TIME_BUCKETS.includes(t as typeof TIME_BUCKETS[number])) return null;
  if (typeof n !== "boolean") return null;
  if (!Array.isArray(a) || a.length > MAX_AD_POS || !a.every((v) => typeof v === "string" && AD_POS.test(v))) return null;
  if (typeof x !== "string" || !EXIT_ZONES.includes(x as ExitZone)) return null;
  if (b !== undefined && !AB_ARMS.includes(b as ReadingArm)) return null;
  if (k !== undefined && (!Array.isArray(k) || k.length > MAX_AD_POS || !k.every((v) => typeof v === "string" && AD_POS.test(v)))) return null;
  const tested = Array.isArray(k) && b !== undefined ? [...new Set(k as string[])] : [];
  return { p, s: s as ReadingSource, d, t, n, a: [...new Set(a as string[])], x: x as ExitZone, ...(tested.length ? { b: b as ReadingArm, k: tested } : {}) };
}
