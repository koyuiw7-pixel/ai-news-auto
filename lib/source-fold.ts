/**
 * 本文の終わりの「出典の一覧」を小さくたたむ（2026-11-10 オーナー「出典はこんなに大きくいらない。表示すればいいだけなのに
 * メインの内容みたいになっている。読む場所が分かりづらい」。台帳 W37）。
 *
 * 「計算の出典は次のとおりです。」「出典」「参考資料」などの短い前置き（段落か見出し）のすぐ後の一覧（ul / ol）を、
 * 閉じた <details>「出典を見る（N件）」に入れる。中身は HTML に残す（検索エンジンにも読める。出典は消さない＝うそをつかない決まり）。
 * 一覧の中で URL そのものがリンクの文字になっている項目（「国税庁のタックスアンサー No.2523（https://…）」）は、
 * 前の名前をリンクの文字にし、URL は href にだけ残す（長い URL を画面に並べない）。名前が無い項目はドメインを文字にする。
 * 構造化データ（JSON-LD）の出典はここでは触らない。
 */

/** 出典の前置き（段落）。短い1文だけ（本文の段落を巻き込まない） */
const LEAD_RE =
  /^(?:(?:計算|数字|記事|この記事|本記事)の)?(?:主な)?(?:出典|参考(?:資料|文献|リンク|にした(?:資料|ページ))?|情報源|確認した資料)(?:は次の(?:とおり|通り)(?:です)?|一覧|：|:)?[。．：:]?$/;

// 前置きの中身は、別の段落・見出しをまたがない（またぐと長い範囲を1つに飲み込み、後ろの本物の前置きを見落とす）
const LIST_AFTER_LEAD_RE = /<(p|h2|h3|h4)\b([^>]*)>((?:(?!<\/?(?:p|h2|h3|h4)\b)[\s\S])*)<\/\1>\s*(<(ul|ol)\b[^>]*>[\s\S]*?<\/\5>)/gi;

function plain(html: string): string {
  return html
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, "")
    .trim();
}

function hostOf(url: string): string {
  try {
    return new URL(url.replace(/&amp;/g, "&")).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** a の文字が URL そのものなら、前の名前（無ければドメイン）を文字にする */
function tidyItem(li: string): string {
  // 名前（全角・半角のかっこ）＋ URL のリンク → 名前をリンクに
  let out = li.replace(
    /(<li\b[^>]*>)\s*([^<]*?[^\s（(])\s*[（(]\s*<a\b([^>]*)>\s*(https?:\/\/[^<\s]+)\s*<\/a>\s*[）)]/gi,
    (_m, open: string, name: string, attrs: string, url: string) =>
      `${open}<a${attrs}>${name.trim()}</a><span class="src-host">${hostOf(url)}</span>`,
  );
  // 残る「URL そのものの文字」はドメインにする（href はそのまま）
  out = out.replace(/<a\b([^>]*)>\s*(https?:\/\/[^<\s]+)\s*<\/a>/gi, (_m, attrs: string, url: string) => `<a${attrs}>${hostOf(url)}</a>`);
  return out;
}

export function foldSourceLists(html: string): string {
  if (!html || !/出典|参考|情報源|確認した資料/.test(html)) return html;
  return html.replace(LIST_AFTER_LEAD_RE, (whole, tag: string, attrs: string, inner: string, list: string) => {
    const lead = plain(inner);
    if (lead.length === 0 || lead.length > 24 || !LEAD_RE.test(lead)) return whole;
    const items = list.match(/<li\b/gi)?.length ?? 0;
    if (items === 0) return whole;
    const tidied = list
      .replace(/^<(ul|ol)\b[^>]*>/i, (open) => open.replace(/^<(ul|ol)/i, '<$1 class="src-list"'))
      .replace(/<li\b[^>]*>[\s\S]*?<\/li>/gi, tidyItem);
    const fold = `<details class="src-fold"><summary>出典を見る（${items}件）</summary>${tidied}</details>`;
    // 見出しの前置き（## 出典）は目次の行き先なので残し、一覧だけをたたむ。段落の前置きは「出典を見る」に置き換える
    return /^h/i.test(tag) ? `<${tag}${attrs}>${inner}</${tag}>${fold}` : fold;
  });
}
