import { promises as fs } from "@/lib/content-fs";
import path from "node:path";
import { ImageResponse } from "next/og";
import sharp from "sharp";
import { getAllArticles, getArticle, PRERENDER_LIMIT } from "@/lib/articles";
import { fetchPhoto } from "@/lib/cover";
import { aiCreditText } from "@/lib/image-credit";
import { siteConfig } from "@/site.config";
import { PHOTO_SHARE_HEIGHT as HEIGHT, PHOTO_SHARE_WIDTH as WIDTH, photoCover } from "@/lib/share-image";

/**
 * 表紙の写真の共有画像（1200×675・16:9。2026-11-10 Google Discover の準備）。
 *
 * Discover は幅 1,200px 以上の大きな画像の記事を大きなカードで出し、Google は「文字の多い画像は避ける」と案内している。
 * 公式の写真が無い記事は、これまで見出しの文字入りのカバー（/cover/<slug>）や数字の図を共有画像にしていた。
 * 表紙に出している写真のイメージ（coverImage。Muse の写真など。lib/share-image.ts の photoCover）がある記事は、
 * その写真に「画像はイメージ（AI生成）」の札だけを付けて出す（台帳 I4。AI の絵には必ず札を付ける）。見出しの文字は重ねない。
 * URL は /cover/ の下なので、Workers のフォントの先読み・エッジのキャッシュ（cloudflare/worker.ts）はカバーと同じ。
 */
export const dynamic = "force-static";
export const dynamicParams = true;
export const revalidate = 604800;

export function generateStaticParams() {
  return getAllArticles()
    .slice(0, PRERENDER_LIMIT)
    // 一覧の要約には表紙の欄（coverImage）が無いので、記事の JSON を読んで決める
    .filter((article) => photoCover(getArticle(article.slug) ?? article))
    .map((article) => ({ slug: article.slug }));
}

const FONT_DIR = path.join(process.cwd(), "assets", "fonts");
const JPEG_QUALITY = 84;
const CACHE_HEADERS = {
  "Content-Type": "image/jpeg",
  "Cache-Control": "public, max-age=604800, s-maxage=604800, stale-while-revalidate=86400, immutable",
};

let font: Promise<Buffer> | null = null;
function loadFont() {
  font ??= fs.readFile(path.join(FONT_DIR, "NotoSansJP-Bold.otf"));
  return font;
}

/** 写真を 1200×675 に切り抜いた data URL（sharp が無い Workers では URL のまま敷く） */
async function photoSource(url: string): Promise<string | null> {
  try {
    const photo = await fetchPhoto(url);
    if (photo) {
      const jpeg = await sharp(photo).resize(WIDTH, HEIGHT, { fit: "cover", position: "attention" }).jpeg({ quality: 90 }).toBuffer();
      return `data:image/jpeg;base64,${jpeg.toString("base64")}`;
    }
  } catch {
    // sharp が無い（Workers）: 下で URL のまま敷く
  }
  // fetchPhoto は sharp で画像を確かめるので、Workers では取れても null になる。サイトの画像の URL はそのまま敷く
  return /^https:\/\//.test(url) ? url : null;
}

async function renderPhoto(cover: string, label: string): Promise<Response | null> {
  const src = await photoSource(cover);
  if (!src) return null;
  const image = new ImageResponse(
    (
      <div style={{ width: WIDTH, height: HEIGHT, display: "flex", position: "relative", background: "#111" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt="" width={WIDTH} height={HEIGHT} style={{ position: "absolute", left: 0, top: 0, objectFit: "cover" }} />
        <div
          style={{
            position: "absolute",
            left: 28,
            bottom: 26,
            display: "flex",
            fontFamily: "Noto",
            fontSize: 20,
            fontWeight: 700,
            color: "#ffffff",
            padding: "5px 12px",
            borderRadius: 6,
            background: "rgba(6,14,32,0.72)",
          }}
        >
          {label}
        </div>
      </div>
    ),
    { width: WIDTH, height: HEIGHT, fonts: [{ name: "Noto", data: await loadFont(), weight: 700 }] },
  );
  const png = await image.arrayBuffer();
  try {
    const jpeg = await sharp(Buffer.from(png)).flatten({ background: "#111111" }).jpeg({ quality: JPEG_QUALITY, mozjpeg: true }).toBuffer();
    return new Response(new Uint8Array(jpeg), { headers: CACHE_HEADERS });
  } catch {
    // Cloudflare Workers（sharp なし）では PNG のまま返す
    return new Response(png, { headers: { ...CACHE_HEADERS, "Content-Type": "image/png" } });
  }
}

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = getArticle(slug);
  const cover = article ? photoCover(article) : null;
  if (!article || !cover) return new Response("Not found", { status: 404 });
  // 描けないとき（写真が取れない・描画の失敗）は見出し入りのカバーへ（共有画像を空にしない・ビルドを止めない）
  const fallback = () => Response.redirect(new URL(`/cover/${slug}`, siteConfig.url), 302);
  try {
    return (await renderPhoto(cover, aiCreditText(article.coverCredit) ?? "画像はイメージ（AI生成）")) ?? fallback();
  } catch (error) {
    console.error(`[cover/photo] fallback: ${slug}`, error);
    return fallback();
  }
}
