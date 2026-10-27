"use client";

import Image, { type ImageProps } from "next/image";
import { useState } from "react";
import type { ThumbSource } from "@/lib/companies";

type Stage = "original" | "fallback" | "failed";

const YT_JPG = /^https:\/\/i\.ytimg\.com\/vi\/([^/]+)\/([a-z0-9]+)\.jpg$/;

/** YouTube のサムネイルは同じ画質の WebP（JPEG の約3分の1）で配信する */
function ytWebp(src: string): string {
  const m = YT_JPG.exec(src);
  return m ? `https://i.ytimg.com/vi_webp/${m[1]}/${m[2]}.webp` : src;
}

/**
 * 記事のサムネイル。壊れた画像アイコンを読者に見せないための受け皿を2段持つ。
 *
 * 0. YouTube は軽い WebP 版を先に使う（読めなければ 1 の JPEG 標準画質へ）
 * 1. 高解像度版（maxresdefault）は後から消えることがあるので、読み込めなければ標準画質（hqdefault）へ
 * 2. それも無い（元動画が削除・非公開になった）場合や、画像欄が空の場合は、サイト名入りの代替表示へ
 *
 * 公式ブログ・プレスリリースの記事（source あり）は、企業色の地に発信元名を載せた代替表示にする。
 *
 * 親要素に relative と大きさ（aspect-video など）が指定されている前提で、fill 画像と同じ位置を埋める。
 */
export default function Thumb({ source, ...props }: ImageProps & { source?: ThumbSource }) {
  const original = props.src;
  const empty = typeof original === "string" && original.trim() === "";
  const [stage, setStage] = useState<Stage>(empty ? "failed" : "original");

  if (stage === "failed" && source) {
    return (
      <span
        aria-hidden
        // 写真の代わりの図版。文字の大きさ・コントラストのルールの対象外（docs/typography.md）
        data-decorative=""
        className="@container absolute inset-0 overflow-hidden"
        style={{ background: `linear-gradient(135deg, ${source.color} 0%, color-mix(in srgb, ${source.color} 62%, #000) 100%)` }}
      >
        {source.mark && (
          <span className="absolute -bottom-[14cqw] -right-[4cqw] font-black leading-none tracking-tighter text-white/[0.13] text-[58cqw]">
            {source.mark}
          </span>
        )}
        <span className="absolute left-[6cqw] top-[5.5cqw] font-display text-white/75 text-[max(9px,4.6cqw)]">サイソク</span>
        <span className="absolute inset-x-[6cqw] bottom-[6cqw] flex flex-col gap-[1.6cqw]">
          <span className="w-fit rounded-full bg-white/90 px-[2.4cqw] py-[0.6cqw] font-bold text-ink text-[max(8px,3.4cqw)]">
            公式発表
          </span>
          <span className="line-clamp-2 font-bold leading-[1.3] text-white text-[max(11px,7.4cqw)]">{source.label}</span>
        </span>
      </span>
    );
  }

  if (stage === "failed") {
    return (
      <span aria-hidden data-decorative="" className="absolute inset-0 grid place-items-center bg-surface-2">
        <span className="font-display text-lg text-line-strong">サイソク</span>
      </span>
    );
  }

  const webp = typeof original === "string" ? ytWebp(original) : original;
  const src =
    stage === "fallback" && typeof original === "string"
      ? original.replace("maxresdefault", "hqdefault")
      : webp;

  return (
    <Image
      {...props}
      src={src}
      onError={() => {
        const canFallback =
          stage === "original" &&
          typeof original === "string" &&
          (original.includes("maxresdefault") || webp !== original);
        setStage(canFallback ? "fallback" : "failed");
      }}
    />
  );
}
