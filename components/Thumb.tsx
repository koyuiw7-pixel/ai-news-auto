"use client";

import Image, { type ImageProps } from "next/image";
import { useState } from "react";

type Stage = "original" | "fallback" | "failed";

/**
 * 記事のサムネイル。壊れた画像アイコンを読者に見せないための受け皿を2段持つ。
 *
 * 1. 高解像度版（maxresdefault）は後から消えることがあるので、読み込めなければ標準画質（hqdefault）へ
 * 2. それも無い（元動画が削除・非公開になった）場合や、画像欄が空の場合は、サイト名入りの代替表示へ
 *
 * 親要素に relative と大きさ（aspect-video など）が指定されている前提で、fill 画像と同じ位置を埋める。
 */
export default function Thumb(props: ImageProps) {
  const original = props.src;
  const empty = typeof original === "string" && original.trim() === "";
  const [stage, setStage] = useState<Stage>(empty ? "failed" : "original");

  if (stage === "failed") {
    return (
      <span aria-hidden className="absolute inset-0 grid place-items-center bg-surface-2">
        <span className="font-display text-lg text-line-strong">サイソク</span>
      </span>
    );
  }

  const src =
    stage === "fallback" && typeof original === "string"
      ? original.replace("maxresdefault", "hqdefault")
      : original;

  return (
    <Image
      {...props}
      src={src}
      onError={() => {
        const canFallback =
          stage === "original" &&
          typeof original === "string" &&
          original.includes("maxresdefault");
        setStage(canFallback ? "fallback" : "failed");
      }}
    />
  );
}
