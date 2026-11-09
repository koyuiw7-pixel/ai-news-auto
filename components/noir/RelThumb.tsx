import Thumb from "@/components/Thumb";
import type { ArticleSummary } from "@/lib/articles";
import { containPhoto } from "@/lib/photo-fit";
import { smallThumb } from "@/lib/thumb-url";

/** 写真の無い記事の小さな札の色（ジャンルごと。濃い色に白い文字） */
const GENRE_TINT: Record<string, string> = {
  public: "#1f4e79",
  lifestyle: "#2f6b4f",
  investment: "#6b4a1f",
  business: "#33415c",
  "real-estate": "#5b3d6b",
  ai: "#1d4a8f",
  "tech-gadget": "#2c3e50",
  science: "#22556b",
  sports: "#7a3b2e",
  entertainment: "#6b2f55",
};

/**
 * 記事末の「関連記事」・右の列の「よく読まれている記事」の小さな写真（2026-11-10 の初めての読者の点検: 灰色の空の箱が並んでいた）。
 * 写真は photoOf（記事の写真が無ければ表紙用の AI のイメージ。AI の絵は「AI生成」の札つき）。
 * どちらも無い記事は、灰色の空の箱ではなくジャンル名の入った色の札にする（文字は短く1行で、枠からはみ出さない）
 */
export default function RelThumb({ article, sizes }: { article: ArticleSummary; sizes: string }) {
  const photo = article.photo;
  if (photo) {
    return (
      <Thumb
        src={smallThumb(photo.src)}
        alt=""
        fill
        sizes={sizes}
        pos={photo.pos}
        contain={containPhoto(photo)}
        aiGenerated={Boolean(photo.ai)}
        className="object-cover"
      />
    );
  }
  const tint = GENRE_TINT[article.genreSlug] ?? "#33415c";
  return (
    <span
      data-decorative=""
      data-thumb-failed="empty"
      className="absolute inset-0 grid place-items-center overflow-hidden px-1.5 text-center"
      style={{ background: `linear-gradient(135deg, ${tint} 0%, color-mix(in srgb, ${tint} 70%, #000) 100%)` }}
    >
      <span className="max-w-full truncate text-[11px] font-bold leading-tight text-white/90">{article.genre}</span>
    </span>
  );
}
