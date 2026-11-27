/**
 * 本文の Markdown の「**…**」（1行の中の対）を、marked に渡す前に <strong>…</strong> にする（2026-11-27）。
 *
 * CommonMark の決まりでは、「**「OpenShell」**の」「**無料（0円）**です」のように、閉じの「**」の前が記号（」や））で
 * 後ろが文字のとき太字にならず、生の「**」が読者に見えたり、となりの太字と組みちがえたりしていた（2026-11-27 の点検で 11 本）。
 * 日本語の文では記号のそばの太字がふつうなので、対は先に HTML の太字にする。
 * 触らないもの: コードの区切り（```）の中・`…` の中・伏せ字（「*****」のように3つ以上並ぶ「*」）。
 * 対にならない「**」は scripts/md_markers.py が公開前に消す。
 */
const PAIR = /(?<!\*)\*\*(?!\*)(?=\S)([^*\n]+?)(?<=\S)(?<!\*)\*\*(?!\*)/g;

export function boldToHtml(markdown: string): string {
  if (!markdown.includes("**")) return markdown;
  let fence = false;
  return markdown
    .split("\n")
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        fence = !fence;
        return line;
      }
      if (fence) return line;
      return line
        .split(/(`[^`]*`)/)
        .map((part) => (part.startsWith("`") ? part : part.replace(PAIR, "<strong>$1</strong>")))
        .join("");
    })
    .join("\n");
}
