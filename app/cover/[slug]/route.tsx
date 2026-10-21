import fs from "node:fs/promises";
import path from "node:path";
import { loadDefaultJapaneseParser } from "budoux";
import { ImageResponse } from "next/og";
import { coverPath, getAllArticles, getArticle } from "@/lib/articles";
import { companyOf } from "@/lib/companies";

/**
 * 記事ごとのカバー画像（1200×630）。
 *
 * YouTube のサムネイルをそのまま使うと「よそのコンテンツを貼っただけ」に見えるので、
 * 日本語の見出し・発表元の企業・サイト名を載せた独自の画像を、ビルド時に静的に生成する。
 * SNS（Threads・X）でシェアされたときのカードもこの画像になる。
 * 外部の画像生成APIは使わないので費用はかからない。
 */
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return getAllArticles()
    .filter((article) => coverPath(article))
    .map((article) => ({ slug: article.slug }));
}

const WIDTH = 1200;
const HEIGHT = 630;
const FONT_DIR = path.join(process.cwd(), "assets", "fonts");
const parser = loadDefaultJapaneseParser();

let fonts: Promise<{ name: string; data: Buffer; weight: 700 | 900 }[]> | null = null;
function loadFonts() {
  fonts ??= Promise.all([
    fs.readFile(path.join(FONT_DIR, "ZenKakuGothicNew-Black.ttf")),
    fs.readFile(path.join(FONT_DIR, "ZenKakuGothicNew-Bold.ttf")),
    fs.readFile(path.join(FONT_DIR, "DelaGothicOne-Regular.ttf")),
  ]).then(([black, bold, dela]) => [
    { name: "Zen", data: black, weight: 900 as const },
    { name: "Zen", data: bold, weight: 700 as const },
    { name: "Dela", data: dela, weight: 900 as const },
  ]);
  return fonts;
}

/** 元動画の画像を埋め込み用に取得する。消えていれば標準画質、それも無ければ画像なし */
async function fetchPhoto(url: string): Promise<string | null> {
  const candidates = url.includes("maxresdefault") ? [url, url.replace("maxresdefault", "hqdefault")] : [url];
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      const res = await fetch(candidate, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) continue;
      const type = res.headers.get("content-type") ?? "image/jpeg";
      const data = Buffer.from(await res.arrayBuffer()).toString("base64");
      return `data:${type};base64,${data}`;
    } catch {
      // 取得できなくても画像なしで生成を続ける
    }
  }
  return null;
}

/** 「製品名｜説明」の形なら製品名を強調色に分ける */
function splitTitle(title: string): { head: string; tail: string } {
  const match = /^(.{2,36}?)[｜：|:]\s*(.+)$/.exec(title);
  return match ? { head: match[1], tail: match[2] } : { head: "", tail: title };
}

/** 文字幅のおおよその合計（全角=1、半角=0.56） */
function emWidth(text: string): number {
  let total = 0;
  for (const char of text) total += /[\u0000-\u00ff]/.test(char) ? 0.56 : 1;
  return total;
}

/** 写真の高さ。残りが見出しの帯になる */
const PHOTO_HEIGHT = 400;
const BAND_PADDING = 56;
const BAND_TEXT_WIDTH = WIDTH - BAND_PADDING * 2 - 8;

/** 文節ごとに分け、単語の途中で改行されないようにする */
function Phrases({ text, color, size }: { text: string; color: string; size: number }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", color, fontSize: size, lineHeight: 1.32 }}>
      {parser.parse(text).map((phrase, index) => (
        // 文節の途中で折り返させない（縮ませると文節の中で改行されてしまう）
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
  const isRoundup = article.type === "roundup";
  const title = article.seoTitle || article.title;
  const { head, tail } = splitTitle(title);
  const [photo, fontData] = await Promise.all([fetchPhoto(article.thumbnail), loadFonts()]);

  // 製品名は1行に収める。長ければ文字を小さくする
  const headSize = Math.min(66, Math.floor(BAND_TEXT_WIDTH / Math.max(emWidth(head), 1)));
  const tailSize = head ? 46 : emWidth(tail) <= 16 ? 62 : 52;

  return new ImageResponse(
    (
      <div
        style={{
          width: WIDTH,
          height: HEIGHT,
          display: "flex",
          flexDirection: "column",
          background: "#ffffff",
          fontFamily: "Zen",
          fontWeight: 900,
        }}
      >
        {/* 上：元動画の写真をそのままの明るさで大きく見せる */}
        <div
          style={{
            position: "relative",
            display: "flex",
            width: WIDTH,
            height: PHOTO_HEIGHT,
            background: company.slug === "other" ? "#111111" : company.color,
            overflow: "hidden",
          }}
        >
          {/* 元動画が削除されて写真が無いときは、企業色の地に企業名を大きく敷く */}
          {!photo && (
            <div
              style={{
                position: "absolute",
                left: 40,
                bottom: -40,
                display: "flex",
                fontSize: 220,
                fontWeight: 900,
                letterSpacing: -6,
                color: "rgba(255,255,255,0.16)",
              }}
            >
              {company.slug === "other" ? "AI NEWS" : company.name}
            </div>
          )}
          {photo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo}
              alt=""
              width={WIDTH}
              height={PHOTO_HEIGHT}
              style={{ width: WIDTH, height: PHOTO_HEIGHT, objectFit: "cover", objectPosition: "center 35%" }}
            />
          )}

          {/* 発表元と種類のバッジ。写真の上でも読めるよう白地に載せる */}
          <div style={{ position: "absolute", left: 40, top: 36, display: "flex", gap: 12 }}>
            {company.slug !== "other" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 22px 10px 12px",
                  borderRadius: 999,
                  background: "#ffffff",
                  boxShadow: "0 6px 24px rgba(0,0,0,0.18)",
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: company.color,
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: company.mark.length > 1 ? 17 : 22,
                    fontWeight: 700,
                  }}
                >
                  {company.mark}
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#111" }}>{company.name}</div>
              </div>
            )}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "10px 22px",
                borderRadius: 999,
                fontSize: 26,
                fontWeight: 700,
                background: isRoundup ? "#111111" : "#e5372b",
                color: "#ffffff",
                boxShadow: "0 6px 24px rgba(0,0,0,0.18)",
              }}
            >
              {isRoundup ? `${article.sources?.length ?? 0}本の発表を統合` : "速報"}
            </div>
          </div>

          {/* サイト名。右上に小さく、黒い札で */}
          <div
            style={{
              position: "absolute",
              right: 40,
              top: 36,
              display: "flex",
              alignItems: "center",
              padding: "10px 22px",
              borderRadius: 14,
              background: "#111111",
              color: "#ffffff",
              fontFamily: "Dela",
              fontSize: 30,
            }}
          >
            サイソク
          </div>
        </div>

        {/* 写真と見出しの境目に、発表元の企業色 */}
        <div style={{ display: "flex", width: WIDTH, height: 8, background: company.color }} />

        {/* 下：白地に見出し。製品名は黄色のマーカーで強調（サイトと同じ表現） */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            gap: 8,
            padding: `0 ${BAND_PADDING}px`,
          }}
        >
          {head && (
            <div style={{ display: "flex" }}>
              <div
                style={{
                  display: "flex",
                  fontSize: headSize,
                  lineHeight: 1.2,
                  color: "#111111",
                  backgroundImage: "linear-gradient(transparent 62%, #ffe873 62%)",
                  padding: "0 4px",
                }}
              >
                {head}
              </div>
            </div>
          )}
          <Phrases text={tail} color={head ? "#3b3b37" : "#111111"} size={tailSize} />
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
