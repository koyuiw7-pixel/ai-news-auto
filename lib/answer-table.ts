/**
 * 記事の「答えの表」（早見表など）を、要点のすぐ下に出すために本文から取り出す（2026-11-11 オーナー「弱点になるなら全部改善して」・読者目線レビュー 3位）。
 * 12月の児童手当の記事では、読者がいちばん知りたい「子の人数と年齢別の早見表」がスマホで上から約4.8画面目だった。
 *
 * 取り出すのは、本文の最初の2章（3つ目の h2 より前）にある最初の表で、スマホで読める大きさ（列4つまで・行13まで）のものだけ。
 * 表の場所には「表は記事の最初にあります」の1行を残す（同じ表を2回並べない）。比較記事の表（提携先の一覧が表の直後に付く）は動かさない。
 */
export type AnswerTable = {
  /** 表の HTML（本文の囲み <div class="…"> ごと） */
  html: string;
  /** 表の見出し（表のある章の h2 の文字。無ければ「早見表」） */
  caption: string;
  /** 表を取り出したあとの本文 */
  rest: string;
};

export const ANSWER_TABLE_ID = "answer-table";
const MAX_COLS = 4;
const MAX_ROWS = 13;

const textOf = (html: string) => html.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();

export function extractAnswerTable(html: string): AnswerTable | null {
  if (!html) return null;
  // 3つ目の h2 より前だけを見る
  const heads = [...html.matchAll(/<h2\b/g)].map((m) => m.index ?? 0);
  const limit = heads.length >= 3 ? heads[2] : html.length;
  const start = html.indexOf("<table");
  if (start < 0 || start >= limit) return null;
  const end = html.indexOf("</table>", start);
  if (end < 0) return null;
  let from = start;
  let to = end + "</table>".length;
  // 本文の囲み（<div class="nr-scroll …"><table>…</table></div>）ごと取り出す
  const before = html.slice(0, start);
  const wrap = /<div\b[^>]*>\s*$/.exec(before);
  const after = /^\s*<\/div>/.exec(html.slice(to));
  if (wrap && after) {
    from = wrap.index;
    to += after[0].length;
  }
  const block = html.slice(from, to);
  const firstRow = /<tr\b[\s\S]*?<\/tr>/.exec(block)?.[0] ?? "";
  const cols = (firstRow.match(/<t[hd]\b/g) ?? []).length;
  const rows = (block.match(/<tr\b/g) ?? []).length;
  if (cols < 2 || cols > MAX_COLS || rows < 2 || rows > MAX_ROWS) return null;
  // 表のある章の見出し（表より前のいちばん近い h2）
  const h2s = [...html.slice(0, from).matchAll(/<h2\b[^>]*>([\s\S]*?)<\/h2>/g)];
  const caption = h2s.length > 0 ? textOf(h2s[h2s.length - 1][1]) : "早見表";
  const note = `<p class="answer-table-moved"><a href="#${ANSWER_TABLE_ID}">表は記事の最初（要点の下）にあります</a></p>`;
  return { html: block, caption: caption || "早見表", rest: html.slice(0, from) + note + html.slice(to) };
}
