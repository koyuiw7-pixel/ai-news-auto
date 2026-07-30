import { marked } from "marked";

marked.setOptions({ gfm: true, breaks: false });

/**
 * 生成AIの出力をそのまま dangerouslySetInnerHTML に流すため、
 * スクリプト実行につながる要素・属性を最小限のホワイトリスト方針で除去する。
 */
function sanitize(html: string): string {
  return html
    .replace(/<\s*(script|style|iframe|object|embed|form)\b[\s\S]*?<\/\s*\1\s*>/gi, "")
    .replace(/<\s*(script|style|iframe|object|embed|form|link|meta)\b[^>]*>/gi, "")
    .replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "")
    .replace(/\son[a-z]+\s*=\s*[^\s>]+/gi, "")
    .replace(/(href|src)\s*=\s*"\s*javascript:[^"]*"/gi, '$1="#"')
    .replace(/(href|src)\s*=\s*'\s*javascript:[^']*'/gi, "$1='#'");
}

/** 外部リンクに rel/target を付与 */
function hardenLinks(html: string): string {
  return html.replace(
    /<a\s+href="(https?:\/\/[^"]+)"/gi,
    '<a href="$1" target="_blank" rel="noopener noreferrer nofollow"',
  );
}

export async function renderMarkdown(markdown: string): Promise<string> {
  const html = await marked.parse(markdown ?? "");
  return hardenLinks(sanitize(html));
}

/** 記事本文から目次（h2）を抽出 */
export function extractHeadings(markdown: string): { id: string; text: string }[] {
  const headings: { id: string; text: string }[] = [];
  const lines = (markdown ?? "").split("\n");
  let inCodeBlock = false;

  for (const line of lines) {
    if (/^\s*```/.test(line)) {
      inCodeBlock = !inCodeBlock;
      continue;
    }
    if (inCodeBlock) continue;

    const match = /^##\s+(.+?)\s*$/.exec(line);
    if (!match) continue;
    const text = match[1].replace(/[*_`]/g, "").trim();
    headings.push({ id: slugifyHeading(text), text });
  }
  return headings;
}

/** marked のデフォルト heading id 生成に合わせる */
export function slugifyHeading(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/<[!\/a-z].*?>/gi, "")
    .replace(/[ -⁯⸀-⹿\\'!"#$%&()*+,./:;<=>?@[\]^`{|}~]/g, "")
    .replace(/\s/g, "-");
}
