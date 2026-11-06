/**
 * 新しい記事の見た目「ノワール」（2026-11-07 オーナー承認・台帳 W36）の決まりと、本文 HTML の仕上げ。
 *
 * - 見た目を切り替えるのは記事 JSON の `layout: "noir"` だけ（scripts/noir_layout.py が新しい記事を書き出すときに付ける）。
 *   印の無い今までの記事は、今までの見た目のまま（app/articles/[slug]/page.tsx の分かれ道）。
 * - 要点の欄（summaryLine・keyFigure・changes・wrapUp）は、品質ゲートを通った本文・要点から決まった手順で抜き出したもの。
 *   どれも任意で、無ければその部品を出さない（空の囲みを出さない）。
 */
import type { Article } from "@/lib/articles";

export const NOIR_LAYOUT = "noir";

export type NoirKeyFigure = { value: string; unit: string; label?: string; before?: string };
export type NoirChange = { label: string; before: string; after: string; note?: string };
export type NoirWrapItem = { name: string; text: string };

export function isNoir(article: Pick<Article, "layout">): boolean {
  return article.layout === NOIR_LAYOUT;
}

/**
 * 表紙に写真を出すか。公式発表の写真（official）で、大きな文字の無い本物の写真と判定済み（heroOk: true）のものだけ。
 * 告知のバナー・スライド・画面・AI の絵・フリー素材・未判定は出さず、黒い表紙に題名を大きく出す（scripts/images.py の hero_ok）
 */
export function noirPhoto(article: Pick<Article, "thumbnail" | "imageCredit" | "heroOk">): string | null {
  if (!article.thumbnail || article.imageCredit?.kind !== "official" || article.heroOk !== true) return null;
  return article.thumbnail;
}

/** 「**479万7,100円**」の印で、強調する数字と前後の文に分ける */
export function splitEmphasis(line: string): { before: string; em: string | null; after: string } {
  const m = line.match(/^(.*?)\*\*(.+?)\*\*(.*)$/);
  if (!m) return { before: line.replace(/\*\*/g, ""), em: null, after: "" };
  return { before: m[1], em: m[2], after: m[3].replace(/\*\*/g, "") };
}

const ENTITIES: Record<string, string> = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " " };

function plain(html: string): string {
  return html
    .replace(/<[^>]+>/g, "")
    .replace(/&(?:amp|lt|gt|quot|#39|nbsp);/g, (e) => ENTITIES[e] ?? e)
    .replace(/\*\*|`/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function rowsOf(table: string): string[][] {
  return Array.from(table.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi), (row) =>
    Array.from(row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi), (cell) => plain(cell[1])),
  );
}

const TABLE_RE = /<table[^>]*>[\s\S]*?<\/table>/gi;

/** 「まだ分からないこと」の章（オーナーが新しい見た目では出さないと決めた章。2026-11-07） */
const UNKNOWN_SECTION = /^まだ(?:分|わ)からない(?:こと|点)/;

/** 見出し（h2）ごとに分けた本文から、名前の合う章を外す */
function dropSections(html: string, test: RegExp): string {
  const parts = html.split(/(?=<h2[\s>])/i);
  return parts
    .filter((part) => {
      const h = part.match(/^<h2[^>]*>([\s\S]*?)<\/h2>/i);
      return !(h && test.test(plain(h[1])));
    })
    .join("");
}

function changesHtml(changes: NoirChange[]): string {
  const rows = changes
    .map(
      (c) =>
        `<div class="nr-c"><small>${escapeHtml(c.label)}</small><p><s>${escapeHtml(c.before)}</s><i aria-label="から">→</i><b>${escapeHtml(c.after)}</b>${
          c.note ? `<span class="nr-cnote">${escapeHtml(c.note)}</span>` : ""
        }</p></div>`,
    )
    .join("");
  return `<div class="nr-chg rv" data-dense="">${rows}</div>`;
}

function wrapHtml(items: NoirWrapItem[]): string {
  return `<ul class="nr-line rv" data-dense="">${items.map((i) => `<li><b>${escapeHtml(i.name)}</b><span>${escapeHtml(i.text)}</span></li>`).join("")}</ul>`;
}

/**
 * ノワールの本文 HTML の仕上げ（今までの記事には使わない）。
 * ①「まだ分からないこと」の章を外す ②「前／今回」の表を「前 → 今」の行に ③最後の章の「名前｜説明」の表を一覧に
 * ④残る2列の表は細い線の表（.nr-price）に、3列以上の表は横に動かせる枠に入れる（スマホで文字を折り返して崩さない）
 * ⑤段落・見出し・引用に、読み進めると現れる印（.rv）を付ける
 */
export function noirBodyHtml(html: string, fields: Pick<Article, "changes" | "wrapUp">): string {
  let out = dropSections(html, UNKNOWN_SECTION)
    .replace(/<(h2|h3|blockquote)(?=[\s>])/gi, '<$1 data-rv=""')
    .replace(/<p>/gi, '<p data-rv="">');
  const changes = (fields.changes ?? []).filter((c) => c && c.label && c.before && c.after);
  const wrap = (fields.wrapUp ?? []).filter((w) => w && w.name && w.text);
  let changesDone = changes.length === 0;
  let wrapDone = wrap.length === 0;
  out = out.replace(TABLE_RE, (table) => {
    const rows = rowsOf(table);
    if (!changesDone && rows.some((r) => r[0] === changes[0].label && r[1] === changes[0].before && r[2] === changes[0].after)) {
      changesDone = true;
      return changesHtml(changes);
    }
    if (!wrapDone && rows.some((r) => r.length === 2 && r[0] === wrap[0].name && r[1] === wrap[0].text)) {
      wrapDone = true;
      return wrapHtml(wrap);
    }
    const cols = Math.max(0, ...rows.map((r) => r.length));
    if (cols <= 2) return table.replace(/^<table/i, '<table class="nr-price rv"');
    return `<div class="nr-scroll rv">${table}</div>`;
  });
  return out;
}

/** 表紙・要点・見出しで使う文字だけを書体のファイルに含める（Google Fonts の text= で数 KB に絞る） */
export function displayGlyphs(texts: string[]): string {
  const set = new Set<string>();
  for (const text of texts) for (const ch of Array.from(text)) if (!/\s/.test(ch)) set.add(ch);
  for (const ch of Array.from("0123456789,.%→↓サイソク速報")) set.add(ch);
  return Array.from(set).join("");
}

/** 本文の h2 の文字（書体の文字の絞り込み用） */
export function headingTexts(html: string): string[] {
  return Array.from(html.matchAll(/<(h2|h3|blockquote)[^>]*>([\s\S]*?)<\/\1>/gi), (m) => plain(m[2]));
}
