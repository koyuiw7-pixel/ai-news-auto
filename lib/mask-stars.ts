/**
 * 品番などの伏せ字（「C05-*****-******1」のように、ハイフンのすぐ後ろに「*」が3つ以上並ぶ形）は、
 * Markdown の強調の印として読ませない。そのままだと、伏せ字を含む太字（**…C05-*****-******1…**）が
 * 途中で切れて、生の「*」と欠けた太字になる（2026-11-16 issue #155）。
 */
export function protectMaskStars(markdown: string): string {
  return markdown.replace(/(?<=[A-Za-z0-9*]-)\*{3,}/g, (run) => run.replace(/\*/g, "\\*"));
}
