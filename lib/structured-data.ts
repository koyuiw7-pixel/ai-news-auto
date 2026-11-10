/**
 * 構造化データ（JSON-LD）を「ページに見えているもの」と一致させるための小さな決まり（SEO A18）。
 * - VideoObject は、ページの中で再生できる動画（components/ArticleVideo.tsx）があるときだけ出す。
 *   YouTube の動画をもとにした記事は、ページで再生できないので VideoObject にせず、元動画を isBasedOn で示す。
 * - FAQPage は、ページに表示している問いだけから作る（見えない問いを構造化データだけに入れない）。
 */

type VideoInfo = { src: string; poster?: string; seconds?: number; title?: string; uploadedAt?: string };

/** 秒数を ISO 8601 の長さ（PT56S / PT1M30S）にする */
export function isoDuration(seconds: number | undefined): string | undefined {
  if (!seconds || !Number.isFinite(seconds) || seconds <= 0) return undefined;
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `PT${m ? `${m}M` : ""}${s || !m ? `${s}S` : ""}`;
}

const abs = (siteUrl: string, src: string) => (src.startsWith("/") ? `${siteUrl}${src}` : src);

/**
 * ページで再生できる解説動画の VideoObject。動画が無い・再生部品を出さない形のページでは null。
 * uploadDate は記事に動画を足した日時が分かるときだけ入れる（分からない日付を作らない）
 */
export function playableVideoJsonLd(
  video: VideoInfo | null | undefined,
  opts: { rendered: boolean; siteUrl: string; name: string; description: string; fallbackThumbnail?: string; publisherId: string },
): Record<string, unknown> | null {
  if (!opts.rendered || !video?.src) return null;
  const thumb = video.poster || opts.fallbackThumbnail;
  const duration = isoDuration(video.seconds);
  return {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: video.title || opts.name,
    description: opts.description,
    ...(thumb ? { thumbnailUrl: [abs(opts.siteUrl, thumb)] } : {}),
    ...(video.uploadedAt ? { uploadDate: video.uploadedAt } : {}),
    contentUrl: abs(opts.siteUrl, video.src),
    ...(duration ? { duration } : {}),
    inLanguage: "ja",
    publisher: { "@id": opts.publisherId },
  };
}

/**
 * 元の発表・元動画を出典として示す（記事の NewsArticle に足す）。
 * 元動画は VideoObject の形にしない（入れ子でも動画として読まれ、ページで再生できない動画を示すことになるため）
 */
export function sourceJsonLd(source: { url: string; name: string; publisher: string } | null): Record<string, unknown> {
  if (!source?.url) return {};
  return {
    isBasedOn: source.url,
    citation: {
      "@type": "CreativeWork",
      ...(source.name ? { name: source.name } : {}),
      url: source.url,
      ...(source.publisher ? { publisher: { "@type": "Organization", name: source.publisher } } : {}),
    },
  };
}

/** 問いと答えの一覧から FAQPage を作る（空なら null）。渡すのはページに表示している問いだけにする */
export function faqPageJsonLd(items: { q: string; a: string }[]): Record<string, unknown> | null {
  const rows = items.filter((row) => row.q && row.a);
  if (rows.length === 0) return null;
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: rows.map(({ q, a }) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })),
  };
}
