"use client";

import { useEffect } from "react";

/**
 * 閉じた欄（components/DepthBoxes.tsx の Fold = details）の中へのリンク（「手順と公式の窓口を見る ↓」の #steps など）で飛んだとき、
 * その欄を開いてから飛ぶ。ブラウザによっては閉じた details の中へ飛べないため（iPhone の Threads のアプリ内ブラウザなど）。
 * 見た目・位置は変えない（開くのは読者が押したときと、URL の # で来たときだけ）。
 */
export function openFoldFor(hash: string, doc: Pick<Document, "getElementById"> = document): Element | null {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  if (!id) return null;
  const target = doc.getElementById(id);
  if (!target) return null;
  let node: Element | null = target;
  while (node) {
    if (node.tagName === "DETAILS") (node as HTMLDetailsElement).open = true;
    node = node.parentElement;
  }
  return target;
}

export default function FoldOpener() {
  useEffect(() => {
    if (location.hash) openFoldFor(location.hash)?.scrollIntoView();
    const onClick = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest?.('a[href^="#"]') as HTMLAnchorElement | null;
      if (!link) return;
      const target = openFoldFor(link.getAttribute("href") ?? "");
      if (target) {
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", link.getAttribute("href"));
      }
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  return null;
}
