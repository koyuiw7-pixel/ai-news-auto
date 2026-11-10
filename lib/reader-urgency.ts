/**
 * 読者に「自分ごと」として関わる発表かの判定（2026-11-11 読者目線レビュー 6位・11位。依存のない小さなファイル。クライアントの部品からも読める）。
 *
 * 正本は scripts/persona.py の NO_READER_ACTION_RE・READER_URGENT_RE・MEANINGLESS_ACTION_RE（文字列は同じ。tests/test_reader_urgency.cjs が照らし合わせる）。
 *  - 面会・会談・式典・人事・表彰などの発表は、読者がすることが無い。赤い「速報」・トップの見出し・ヘッダー下の帯に出さず、
 *    「すぐにできること」も出さない（財務大臣とベトナム財政大臣の面会に「速報」と「財務省に電話で問い合わせる」が出ていた）
 *  - 赤い「速報」は、暮らしとお金に直接関わる発表（値上げ・給付・障害・流出・リコール・災害など）だけ。AI の発表は今までどおり
 */
export const NO_READER_ACTION_SOURCE =
  "面会|会談|表敬|懇談|締結式|調印式|式典|記念式|授与式|叙勲|褒章|表彰|受賞|視察|再任|就任|退任|人事異動|あいさつ|挨拶|ピッチイベント|公演|講演会|シンポジウム|二国間協力|大臣会合|供用開始|供用予定";

export const READER_URGENT_SOURCE =
  "値上げ|値下げ|価格改定|料金|運賃|給付|手当|補助|助成|支援金|年金|税|控除|保険料|障害(?!者)|不具合|つながりにくい|停止|停電|断水|運休|見合わせ|欠航|流出|漏え?い|漏洩|不正アクセス|不正利用|詐欺|フィッシング|なりすまし|リコール|回収|使用中止|地震|震度|津波|噴火|警報|注意報|台風|大雨|豪雨|線状降水帯|避難|感染|食中毒|締め?切|期限|延長|受付開始|義務化|罰則|金利|利上げ|利下げ|物価|ミサイル|Jアラート|緊急";

export const MEANINGLESS_ACTION_SOURCE =
  "(?:面会|会談|会合|検討会?|会議|協議)(?:の)?(?:詳しい内容|詳細|内容|予定|今後).{0,30}問い合わせ|(?:今後の|次回の?)(?:検討|協議|会議|会合)(?:の)?予定を.{0,10}問い合わせ|ほかの(?:面会|会談|会合)の記録";

const NO_READER_ACTION_RE = new RegExp(NO_READER_ACTION_SOURCE);
const READER_URGENT_RE = new RegExp(READER_URGENT_SOURCE);
const MEANINGLESS_ACTION_RE = new RegExp(MEANINGLESS_ACTION_SOURCE);

/** 面会・会談・式典・人事・表彰などの、読者がすることの無い発表か（題名で判定） */
export function noReaderAction(title: string | null | undefined): boolean {
  return NO_READER_ACTION_RE.test((title ?? "").normalize("NFKC"));
}

/** 赤い「速報」を付けてよい話題か。AI の発表は今までどおり。ほかは暮らしとお金に直接関わる語があるときだけ */
export function urgentForReader(article: { title?: string | null; genreSlug?: string | null }): boolean {
  const title = (article.title ?? "").normalize("NFKC");
  if (noReaderAction(title)) return false;
  if (!article.genreSlug || article.genreSlug === "ai") return true;
  return READER_URGENT_RE.test(title);
}

/** 「面会の詳しい内容を〇〇課に電話で問い合わせる」のような、記事の中身を問い合わせるだけの意味の無い行動か */
export function meaninglessAction(text: string | null | undefined): boolean {
  return MEANINGLESS_ACTION_RE.test(text ?? "");
}

/** 記事に出してよい「すぐにできること」。読者がすることの無い発表は空、意味の無い行動は外す */
export function readerActions<T>(title: string | null | undefined, items: T[], textOf: (item: T) => string): T[] {
  if (noReaderAction(title)) return [];
  return items.filter((item) => !meaninglessAction(textOf(item)));
}
