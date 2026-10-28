/**
 * サムネイルの URL を枠の大きさに合わせて軽い版に替える（クライアント部品からも使う）。
 *
 * - サイトで配信する写真（/img/<名前>.jpg。scripts/images.py が Workers KV に置く）は一覧用の 640px WebP
 * - YouTube は高解像度版（maxresdefault）を標準画質（hqdefault・mqdefault）に
 */
const OWN_IMAGE = /^((?:https:\/\/[^/]+)?\/img\/[A-Za-z0-9][A-Za-z0-9_-]*)\.jpg$/;

export function smallThumb(url: string, youtube: "hqdefault" | "mqdefault" = "hqdefault"): string {
  const own = OWN_IMAGE.exec(url);
  if (own) return `${own[1]}.sm.webp`;
  return url.replace("maxresdefault", youtube);
}

/** 軽い版が読めなかったときの元の画像（替えていなければ null） */
export function largeThumb(url: string): string | null {
  return /\/img\/[A-Za-z0-9][A-Za-z0-9_-]*\.sm\.webp$/.test(url) ? url.replace(/\.sm\.webp$/, ".jpg") : null;
}
