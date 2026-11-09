/**
 * 本文の図（記事 JSON の figures。scripts/map_figures.py が public/fig/<slug>-fig<N>.png から付ける。手で書いてもよい）。
 * 2026-11-09 オーナー「文字だけで写真がない」「続きを読むの部分が文字の壁」: 章の終わりに図を挟んで、本文を区切る。
 * 各図は after_heading の見出しの章の終わり（次の見出しの手前）に置く。見出しが見つからない図は出さない（変な場所に置かない）。
 */
export type ArticleFigure = {
  src: string;
  alt?: string;
  caption?: string;
  /** この見出し（## の文字。言い換え後の見出しでもよい）の章の終わりに置く */
  after_heading?: string;
};

// 自前の画像だけ（/fig/ の静的ファイル・/img/ の KV）。よその URL は出さない
const OK_SRC = /^(?:\/fig\/[\w.-]+|https:\/\/ai-tech-express\.jp\/(?:img|fig)\/[\w.-]+|\/img\/[\w.-]+)\.(?:png|jpe?g|webp)$/i;

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const plain = (html: string) =>
  html
    .replace(/<[^>]+>/g, "")
    .replace(/&[a-z#0-9]+;/gi, "")
    .replace(/[\s「」『』、。・:：]/g, "");

export function usableFigures(figures: ArticleFigure[] | undefined): ArticleFigure[] {
  return (figures ?? []).filter((f) => f && typeof f.src === "string" && OK_SRC.test(f.src)).slice(0, 6);
}

export function figureHtml(fig: ArticleFigure, title: string): string {
  const alt = fig.alt?.trim() || `${title}の図`;
  const caption = fig.caption?.trim();
  return (
    `<figure class="body-figure art-fig not-prose">` +
    `<img src="${esc(fig.src)}" alt="${esc(alt)}" loading="lazy" decoding="async" />` +
    (caption ? `<figcaption class="text-note">${esc(caption)}</figcaption>` : "") +
    `</figure>`
  );
}

/** 本文の HTML に図を差し込む（見出しの文字が合う章の終わりに） */
export function insertArticleFigures(html: string, figures: ArticleFigure[] | undefined, title: string): string {
  const list = usableFigures(figures);
  if (!list.length) return html;
  let out = html;
  for (const fig of list) {
    const want = plain(fig.after_heading ?? "");
    if (!want) continue;
    const heads = Array.from(out.matchAll(/<h2[^>]*>([\s\S]*?)<\/h2>/gi));
    const hit = heads.findIndex((m) => {
      const text = plain(m[1]);
      return text && (text === want || text.includes(want) || want.includes(text));
    });
    if (hit < 0) continue;
    const next = heads[hit + 1];
    const at = next?.index ?? out.length;
    out = out.slice(0, at) + figureHtml(fig, title) + out.slice(at);
  }
  return out;
}
