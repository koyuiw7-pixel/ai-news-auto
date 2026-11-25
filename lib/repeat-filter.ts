/**
 * 決まった欄（なるほど・不安Q&A・判断ガイド・よくある質問）が、記事の結論（リード・要点）の言い直しだけになっていないかの判定
 * （2026-11-25 AdSense「有用性の低いコンテンツ」の点検）。
 *
 * 同じ結論を欄ごとに何度もくり返すと、読者には新しい情報が無く、ページが水増しに見える。
 * 記事のデータは消さず、画面に出す直前に「リード・要点とほぼ同じ文」と「中身の無い短すぎる文」だけを外す。
 * 外す基準はかなり厳しめ（文字の2つ組の重なりが 0.85 以上か、どちらかがもう一方を丸ごと含む）にして、少しでも違う情報がある文は残す。
 */

/** これより短い文（空白・記号を除く）は中身が無いとみなす */
export const MIN_CHARS = 8;
/** 文字の2つ組（bigram）の重なり（Dice 係数）がこれ以上なら「ほぼ同じ」 */
export const NEAR_DUP = 0.85;
/** 丸ごと含む判定に使う最小の長さ（短い語が長い文に含まれるだけでは同じとしない） */
const CONTAIN_MIN = 20;

/** 比べるための形（太字の印・空白・句読点・かっこ・記号を外す） */
export function normalizeForRepeat(text: string): string {
  return String(text ?? "")
    .replace(/\*\*/g, "")
    .replace(/[\s　。、，．,.・「」『』（）()【】［］\[\]！!？?：:；;"'“”‘’〜~\-ー―…]/g, "")
    .toLowerCase();
}

function bigrams(s: string): Map<string, number> {
  const out = new Map<string, number>();
  for (let i = 0; i < s.length - 1; i++) {
    const g = s.slice(i, i + 2);
    out.set(g, (out.get(g) ?? 0) + 1);
  }
  return out;
}

/** 2つの文の重なり（0〜1） */
export function overlap(a: string, b: string): number {
  const x = normalizeForRepeat(a);
  const y = normalizeForRepeat(b);
  if (!x || !y) return 0;
  if (x === y) return 1;
  if (x.length < 2 || y.length < 2) return 0;
  const gx = bigrams(x);
  const gy = bigrams(y);
  let shared = 0;
  for (const [g, n] of gx) shared += Math.min(n, gy.get(g) ?? 0);
  return (2 * shared) / (x.length - 1 + (y.length - 1));
}

/** 中身の無い短すぎる文か */
export function tooShort(text: string): boolean {
  return normalizeForRepeat(text).length < MIN_CHARS;
}

/** refs（リード・要点など）のどれかとほぼ同じ文か */
export function repeatsLead(text: string, refs: readonly (string | null | undefined)[]): boolean {
  const x = normalizeForRepeat(text);
  if (!x) return false;
  for (const ref of refs) {
    const y = normalizeForRepeat(ref ?? "");
    if (!y) continue;
    if (x === y) return true;
    // 丸ごと含む: 短い方が十分に長く、長い方の8割以上を占めるとき（ほぼ同じ文に言葉を少し足しただけ）
    const [short, long] = x.length <= y.length ? [x, y] : [y, x];
    if (short.length >= CONTAIN_MIN && long.includes(short) && short.length / long.length >= 0.8) return true;
    if (overlap(x, y) >= NEAR_DUP) return true;
  }
  return false;
}

/** 欄に出す文として新しい情報が無いか（空・短すぎる・リードや要点の言い直し） */
export function addsNothing(text: string, refs: readonly (string | null | undefined)[]): boolean {
  return !String(text ?? "").trim() || tooShort(text) || repeatsLead(text, refs);
}

/** 記事の結論の文（リード・1文の要約・要点） */
export function leadRefs(a: { lede?: string; summaryLine?: string; highlights?: string[] }): string[] {
  return [a.lede ?? "", a.summaryLine ?? "", ...(a.highlights ?? [])].filter((s) => s.trim().length > 0);
}
