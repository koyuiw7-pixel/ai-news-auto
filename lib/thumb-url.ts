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

/**
 * サイトの写真（/img/<名前>.jpg、1200×630）を枠の幅で選ばせる候補（srcset）。
 * 640 は一覧用 WebP（変換なし）、960・1200 は Cloudflare の画像変換（AVIF/WebP。ゾーン内の画像だけ変換できる）。
 * スマホでも 1200px の JPEG（約130KB）を読んでいたのを 30〜60KB にする（LCP 対策）
 */
export function ownSrcSet(url: string): string | null {
  const own = OWN_IMAGE.exec(url);
  if (!own) return null;
  const path = own[1].replace(/^https:\/\/[^/]+/, "");
  const cdn = (w: number) => `/cdn-cgi/image/width=${w},quality=72,format=auto,fit=scale-down${path}.jpg ${w}w`;
  return `${path}.sm.webp 640w, ${cdn(960)}, ${cdn(1200)}`;
}

const YT_MAXRES_WEBP = /^https:\/\/i\.ytimg\.com\/vi_webp\/([^/]+)\/maxresdefault\.webp$/;

/** YouTube の高解像度サムネイル（1280px・約90KB）。スマホは 640px 版（sddefault・約35KB）で足りる */
export function ytSrcSet(url: string): string | null {
  const m = YT_MAXRES_WEBP.exec(url);
  return m ? `https://i.ytimg.com/vi_webp/${m[1]}/sddefault.webp 640w, ${url} 1280w` : null;
}

/** 軽い版が読めなかったときの元の画像（替えていなければ null） */
export function largeThumb(url: string): string | null {
  return /\/img\/[A-Za-z0-9][A-Za-z0-9_-]*\.sm\.webp$/.test(url) ? url.replace(/\.sm\.webp$/, ".jpg") : null;
}
