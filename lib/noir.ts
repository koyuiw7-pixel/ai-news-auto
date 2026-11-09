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
 * 公式の写真をそのまま表紙に出すか。公式発表の写真（official）で、大きな文字の無い本物の写真と判定済み（heroOk: true）のものだけ。
 * 告知のバナー・スライド・画面・AI の絵・フリー素材・未判定はそのままは出さない（表紙の背景は noirCover が決める。scripts/images.py の hero_ok）
 */
export function noirPhoto(article: Pick<Article, "thumbnail" | "imageCredit" | "heroOk">): string | null {
  if (!article.thumbnail || article.imageCredit?.kind !== "official" || article.heroOk !== true) return null;
  return article.thumbnail;
}

export type NoirCover = {
  /**
   * official: 公式の写真をそのまま全面に／ai: AI のイメージ（「画像はイメージ（AI生成）」を出す）
   * panel: 公式の画像（告知のバナーなど）を、ぼかさず・暗くせずにそのまま見せ、題名はその下の帯に出す
   */
  kind: "official" | "ai" | "panel";
  src: string;
};

/**
 * 表紙の背景（2026-11-07 オーナー「背景は写真を差し込みたい。何もないとただ暗い感じ」「画像反映されていない」。台帳 W36）。順に:
 * ①公式の、大きな文字の無い本物の写真（noirPhoto） ②表紙用の AI のイメージ（coverImage。scripts/noir_cover.py が見出しとのつながりを確かめたものだけ。
 * 見出し画像の AI のイメージも、確かめを通れば coverImage に入る） ③公式・素材の見出し画像（告知のバナーでも）を、くっきりそのまま見せる（panel。
 * 強くぼかして暗くした背景は「画像が無い」ように見えるのでやめた。2026-11-07 午後）
 * どれも無いとき・見出し画像が確かめを通らなかった AI のイメージのときだけ null（明るい紙に題名を大きく）。話題と関係の無い AI の場面は出さない
 */
export function noirCover(
  article: Pick<Article, "thumbnail" | "imageCredit" | "heroOk" | "coverImage" | "coverCredit" | "noPhoto">,
): NoirCover | null {
  const photo = noirPhoto(article);
  if (photo) return { kind: "official", src: photo };
  if (article.noPhoto) return null;
  if (article.coverImage && article.coverCredit?.kind === "ai") return { kind: "ai", src: article.coverImage };
  // 文字だけの見出しカード（card）は写真ではないので表紙に出さない（2026-11-09 オーナー「偽の文字のカードは出さない」）
  if (article.thumbnail && article.imageCredit?.kind !== "ai" && article.imageCredit?.kind !== "card") return { kind: "panel", src: article.thumbnail };
  return null;
}

/** 表紙の AI のイメージに出す札（台帳 I4。scripts/owner_rules_audit.py は「イメージ（AI生成）」の文字で確かめる） */
export const NOIR_AI_LABEL = "画像はイメージ（AI生成）";
/** 公式の画像が無い新製品・サービスの発表で、AI が製品（の種類）を描いた表紙の札（2026-11-07 オーナー） */
export const NOIR_AI_LAUNCH_LABEL = "公式画像がないためイメージ（AI生成）";

/** 表紙の AI のイメージの札の文（coverCredit.launch なら発表の札） */
export function noirAiLabel(article: Pick<Article, "coverCredit">): string {
  return article.coverCredit?.launch ? NOIR_AI_LAUNCH_LABEL : NOIR_AI_LABEL;
}

// 数字の名前が「何の量か」を言っている（scripts/noir_layout.py の MEASURE_LABEL と同じ）
const MEASURE_LABEL = /(数|額|高|費|料|価格|値段|代|金|率|量|時間|期間|規模|売上|利益|収益|予算|賃金|給与|税率|上限|下限|容量|距離|速度|人数|件数|台数)$/;
const LABEL_STOP = /^(約|総額|合計|およそ|前年|今回|昨年|累計で|税込|税抜|税別|米国|日本|国内|海外|世界|全国|計|同|最大|最低|最大で|上限|月額|年額)$/;
const RELATIVE_UNIT = /^(%|％|ポイント|倍)$/;
const flat = (text: string | undefined | null) => String(text ?? "").replace(/\*\*|\s/g, "");

/**
 * 大きな数字の箱を出すか（2026-11-07 オーナー「38% 応答時間 だけでは不自然じゃない？入れなきゃダメみたいなルールないのに」。台帳 W36）。
 * ①前の値（before）があって今と違う、または名前が「何の量か」を言っている（割合・倍は前の値が要る）
 * ②すぐ上の1文（summaryLine）に同じ数字がもう無い。どちらかを満たさなければ箱ごと出さない（今ある記事にも効く。scripts/noir_layout.py の figure_adds_info と同じ）
 */
export function noirKeyFigure(article: Pick<Article, "keyFigure" | "summaryLine">, line?: string | null): NoirKeyFigure | null {
  const fig = article.keyFigure;
  if (!fig || !String(fig.value ?? "").trim()) return null;
  const value = flat(fig.value);
  const unit = flat(fig.unit);
  const label = String(fig.label ?? "").trim();
  const before = flat(fig.before);
  const hasBefore = !!before && before !== value + unit && before !== value;
  if (!hasBefore && (RELATIVE_UNIT.test(unit) || !label || LABEL_STOP.test(label) || !MEASURE_LABEL.test(label))) return null;
  const summary = flat(line ?? article.summaryLine);
  if (summary && summary.includes(value + unit)) return null;
  return fig;
}

/** 「前 → 今」の行は、前と今が違い、名前のある行だけ */
export function noirChanges(changes: NoirChange[] | undefined): NoirChange[] {
  return (changes ?? []).filter((c) => c && c.label && c.before && c.after && flat(c.before) !== flat(c.after));
}

/** まとめの一覧は、説明が名前の言い直しでない行だけ（行の数は作るときに 2〜5 行に決めている） */
export function noirWrapUp(items: NoirWrapItem[] | undefined): NoirWrapItem[] {
  const out = (items ?? []).filter((w) => w && w.name && w.text && flat(w.text).replace(flat(w.name), "").length >= 4);
  return out;
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
    .replace(/<p>/gi, '<p data-rv="">')
    // 数字の入った強調（「月**30,000円**」など）に印を付け、赤い蛍光ペンで目立たせる（2026-11-09 オーナー「大事な数字を目立たせる」）
    .replace(/<strong>(?=[^<]*\d)/gi, '<strong class="nr-num">');
  const changes = noirChanges(fields.changes);
  const wrap = noirWrapUp(fields.wrapUp);
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
