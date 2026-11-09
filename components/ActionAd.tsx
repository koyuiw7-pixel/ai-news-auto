import type { ActionAd as ActionAdData } from "@/lib/action-ad";
import { Pixels, PrFeature, PrRow, PrTag } from "@/components/rail/parts";

/**
 * 「すぐにできること」のすぐ下に置く、編集部の言葉で書いた PR の囲み（1記事に1つ。lib/action-ad.ts）。
 *
 * 2026-11-09 オーナー「PRってこんな大きく書いてる？みんな」: 本文と同じ白地の囲み。広告の表示は右上の小さな「PR」の札と、
 *   囲みの下の注記（ステマ規制の「広告であることが分かる表示」。サイト全体の「本ページはプロモーションを含みます」もある）
 * 2026-11-10 オーナー「広告が魅力的じゃない。わざとらしすぎず、でも目立って押してしまうような」:
 *  - 上の小さな1行は誰に向けた枠か（ad.title）と、記事から商品へつなぐ一文（ad.lead）
 *  - 1つ目は、読者がこの商品で確かめられること（pitch.gain）を見出しにし、良いところ2〜3つ（公式の事実だけ）と色のあるボタン（components/rail/parts.tsx の PrFeature）
 *  - バナーは 6:5 の小さな枠に収める（大きなバナーをそのまま貼らない）。場所は先に取り、読み込みで画面がずれない。ポップアップは出さない
 *  - 2つ目は小さく1行
 * クリックは data-aff-pos="action-ad"（components/AffClickTracker.tsx → cloudflare/aff.ts の byPlacement）で、置き場所×提携先ごとに数える。
 * data-ad-ab のある枠は、ボタンの色の A/B（<html data-adv>）もいっしょに送る（byVariant）。
 */
export default function ActionAd({ ad, className = "mt-4" }: { ad: ActionAdData; className?: string }) {
  if (ad.items.length === 0) return null;
  const [first, ...rest] = ad.items;
  const lead = ad.lead ?? ad.reason;
  return (
    <aside
      data-aff-pos="action-ad"
      data-action-ad={ad.key}
      data-ad-ab=""
      aria-label="PR：広告"
      className={`relative max-w-[40em] overflow-hidden rounded-2xl border border-line bg-paper shadow-[0_1px_2px_rgb(11_26_51/0.05)] ${className}`}
    >
      <div className="border-b border-line px-4 pt-3 pb-3 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 text-meta font-bold leading-snug text-ink-soft">{ad.title}</p>
          <PrTag />
        </div>
        {/* 記事から商品へつなぐ一文。スマホは省いて囲みを低くする（見出しの1行が誰向けかを示す） */}
        {lead && <p className="mt-1 hidden text-note leading-[1.65] text-ink-soft sm:block">{lead}</p>}
      </div>

      <PrFeature item={first.item} wide />

      {rest.length > 0 && (
        <ul className="border-t border-line">
          {rest.map(({ item }, index) => (
            <li key={item.key} className="border-b border-line last:border-b-0">
              <PrRow item={item} rank={index + 2} />
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-line bg-surface px-4 py-2.5 text-note leading-relaxed text-muted sm:px-6">
        広告（アフィリエイトリンク）を含みます。申し込みがあると当サイトに紹介料が入ることがあります。料金・条件は各公式サイトで確認してください。
      </p>
      <Pixels pixels={ad.items.map(({ pixel }) => pixel).filter((p): p is string => Boolean(p))} />
    </aside>
  );
}
