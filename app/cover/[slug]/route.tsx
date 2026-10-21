import fs from "node:fs/promises";
import path from "node:path";
import { loadDefaultJapaneseParser } from "budoux";
import { ImageResponse } from "next/og";
import { coverPath, getAllArticles, getArticle } from "@/lib/articles";
import { companyOf } from "@/lib/companies";
import {
  basePhoto,
  COVER_HEIGHT as HEIGHT,
  COVER_WIDTH as WIDTH,
  fetchPhoto,
  toDataUrl,
  withBottomShade,
} from "@/lib/cover";

/**
 * 記事ごとのカバー画像（1200×630）。
 *
 * YouTube のサムネイルをそのまま使うと「よそのコンテンツを貼っただけ」に見えるので、
 * 日本語の見出し・発表元の企業・サイト名を載せた独自の画像を、ビルド時に静的に生成する。
 * SNS（Threads・X）でシェアされたときのカードもこの画像になる。
 * 外部の画像生成APIは使わないので費用はかからない。
 *
 * デザインは報道テロップ型：写真は加工せず、下だけ自然に暗くして白い極太の見出しを載せる。
 * 左に発表元の企業色の縦線、見出しの上に赤い「速報」ラベル。
 */
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return getAllArticles()
    .filter((article) => coverPath(article))
    .map((article) => ({ slug: article.slug }));
}

const FONT_DIR = path.join(process.cwd(), "assets", "fonts");
const parser = loadDefaultJapaneseParser();

const MARGIN = 56;
const BAR = 8;
const BAR_GAP = 24;
const TEXT_WIDTH = WIDTH - MARGIN * 2 - BAR - BAR_GAP;
const SHADOW = "0 2px 14px rgba(0,0,0,0.35)";

let fonts: Promise<{ name: string; data: Buffer; weight: 400 | 700 | 900 }[]> | null = null;
function loadFonts() {
  fonts ??= Promise.all([
    fs.readFile(path.join(FONT_DIR, "NotoSansJP-Black.otf")),
    fs.readFile(path.join(FONT_DIR, "NotoSansJP-Bold.otf")),
    fs.readFile(path.join(FONT_DIR, "DelaGothicOne-Regular.ttf")),
  ]).then(([black, bold, dela]) => [
    { name: "Noto", data: black, weight: 900 as const },
    { name: "Noto", data: bold, weight: 700 as const },
    { name: "Dela", data: dela, weight: 400 as const },
  ]);
  return fonts;
}

/** 「製品名｜説明」の形なら、製品名を大見出し・説明を小見出しに分ける */
function splitTitle(title: string): { head: string; tail: string } | null {
  const match = /^(.{2,36}?)[｜：|:]\s*(.+)$/.exec(title);
  return match ? { head: match[1], tail: match[2] } : null;
}

/** 文字幅のおおよその合計（全角=1、半角=0.56） */
function emWidth(text: string): number {
  let total = 0;
  for (const char of text) total += /[\u0000-ÿ]/.test(char) ? 0.56 : 1;
  return total;
}

/** 文節ごとに分け、単語の途中で改行されないようにする */
function Phrases({
  text,
  size,
  weight,
  color,
}: {
  text: string;
  size: number;
  weight: 700 | 900;
  color: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        fontSize: size,
        fontWeight: weight,
        lineHeight: 1.3,
        color,
        textShadow: SHADOW,
      }}
    >
      {parser.parse(text).map((phrase, index) => (
        // 縮ませると文節の中で改行されてしまうので固定する
        <span key={index} style={{ display: "flex", flexShrink: 0 }}>
          {phrase}
        </span>
      ))}
    </div>
  );
}

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article || !coverPath(article)) return new Response("Not found", { status: 404 });

  const company = companyOf(article);
  const isOther = company.slug === "other";
  const label = article.type === "roundup" ? `${article.sources?.length ?? 0}本の発表を統合` : "速報";
  const title = article.seoTitle || article.title;
  const parts = splitTitle(title);

  const [photo, fontData] = await Promise.all([fetchPhoto(article.thumbnail), loadFonts()]);
  const base = await basePhoto(photo, isOther ? "#1d1d22" : company.color);
  const background = await toDataUrl(await withBottomShade(base, 0.38, 0.88));

  // 製品名は1行に収める（長ければ小さくする）
  const headSize = parts ? Math.min(58, Math.floor(TEXT_WIDTH / Math.max(emWidth(parts.head), 1))) : 0;

  return new ImageResponse(
    (
      <div
        style={{
          width: WIDTH,
          height: HEIGHT,
          display: "flex",
          position: "relative",
          background: "#111",
          fontFamily: "Noto",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={background} alt="" width={WIDTH} height={HEIGHT} style={{ position: "absolute", left: 0, top: 0 }} />

        {/* 元動画が削除されて写真が無いときは、企業色の地に企業名を大きく敷く */}
        {!photo && (
          <div
            style={{
              position: "absolute",
              left: 48,
              top: 70,
              display: "flex",
              fontSize: 200,
              fontWeight: 900,
              letterSpacing: -4,
              color: "rgba(255,255,255,0.14)",
            }}
          >
            {isOther ? "AI NEWS" : company.name}
          </div>
        )}

        {/* サイト名 */}
        <div
          style={{
            position: "absolute",
            right: 48,
            top: 40,
            display: "flex",
            fontFamily: "Dela",
            fontSize: 28,
            color: "#fff",
            textShadow: "0 2px 10px rgba(0,0,0,0.45)",
          }}
        >
          サイソク
        </div>

        {/* 見出し：左に企業色の縦線、上に赤いラベル */}
        <div
          style={{
            position: "absolute",
            left: MARGIN,
            bottom: MARGIN,
            width: WIDTH - MARGIN * 2,
            display: "flex",
            gap: BAR_GAP,
          }}
        >
          <div style={{ width: BAR, borderRadius: BAR / 2, background: isOther ? "#d92d20" : company.color }} />
          <div style={{ width: TEXT_WIDTH, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 23, fontWeight: 700, color: "#fff" }}>
              <div style={{ display: "flex", padding: "3px 13px", borderRadius: 4, background: "#d92d20" }}>{label}</div>
              {!isOther && <div style={{ display: "flex", textShadow: SHADOW }}>{company.name}</div>}
            </div>

            {parts ? (
              // 画像の描画エンジンは <></> を正しく縦に並べないので、明示的に縦並びの箱で包む
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div
                  style={{
                    display: "flex",
                    fontSize: headSize,
                    fontWeight: 900,
                    lineHeight: 1.25,
                    color: "#fff",
                    textShadow: SHADOW,
                  }}
                >
                  {parts.head}
                </div>
                <Phrases text={parts.tail} size={31} weight={700} color="rgba(255,255,255,0.9)" />
              </div>
            ) : (
              <Phrases text={title} size={emWidth(title) <= 18 ? 58 : 50} weight={900} color="#fff" />
            )}
          </div>
        </div>
      </div>
    ),
    {
      width: WIDTH,
      height: HEIGHT,
      fonts: fontData,
      headers: { "Cache-Control": "public, max-age=31536000, immutable" },
    },
  );
}
