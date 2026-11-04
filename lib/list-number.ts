// 番号つきの並び（<ol class="num-list">）に入れる文字の、頭の番号を外す（2026-11-05 台帳 A45）。
// 番号は CSS で描くので、文字の頭に「1. 」「１．」「①」「(1)」があると「1. 1〜」と二重になる。
// 「3.5GHz帯」「23.8兆」のような数字の小数は外さない（番号の後に数字が続くものは番号とみなさない）
const LIST_NUMBER_RE = /^\s*(?:[(（]\s*[0-9０-９]{1,2}\s*[)）]|[0-9０-９]{1,2}\s*[.．)）、:：](?![0-9０-９])|[①-⑳])\s*/;

export function stripListNumber(text: string): string {
  const value = String(text ?? "");
  const stripped = value.replace(LIST_NUMBER_RE, "");
  return stripped.trim() ? stripped : value;
}
