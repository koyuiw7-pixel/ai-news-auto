import type { ReactNode } from "react";

/*
 * 見出しの「要点」に蛍光ペンを引く。
 * 優先順: 「」で囲まれた製品名・機能名 → 単位付きの数字（15万行、3200万ドル など）。
 * どちらも無ければ何もしない（無理に引くと画面がうるさくなるため）。
 */

const QUOTED = /「([^」]{2,24})」/;
const FIGURE =
  /\d[\d,.]*(?:万|億|兆)?(?:行|ドル|円|%|％|倍|本|件|人|時間|パラメータ)/;

export function Highlight({ text }: { text: string }): ReactNode {
  const quoted = QUOTED.exec(text);
  if (quoted) {
    const start = quoted.index + 1;
    const end = start + quoted[1].length;
    return (
      <>
        {text.slice(0, start)}
        <mark>{quoted[1]}</mark>
        {text.slice(end)}
      </>
    );
  }

  const figure = FIGURE.exec(text);
  if (figure) {
    const start = figure.index;
    const end = start + figure[0].length;
    return (
      <>
        {text.slice(0, start)}
        <mark>{figure[0]}</mark>
        {text.slice(end)}
      </>
    );
  }

  return text;
}
