/**
 * 提携リンクのクリックを数えるときの提携先の ID（components/AffClickTracker.tsx が送る p）。
 * A8 は a8mat（楽天アフィリエイトの rpx.a8.net のリンクも、楽天の a8mat で数える）、それ以外はドメイン。
 */
export function programOf(href: string): string {
  try {
    const url = new URL(href);
    const a8mat = url.searchParams.get("a8mat");
    // a8mat の「+」は URLSearchParams で空白に化けるので戻す
    if (a8mat) return a8mat.replace(/ /g, "+").slice(0, 60);
    if (/(^|\.)afl\.rakuten\.co\.jp$/.test(url.hostname)) return "rakuten";
    if (/amazon\.|amzn\.to$/.test(url.hostname)) return "amazon";
    return url.hostname.slice(0, 60);
  } catch {
    return "unknown";
  }
}
