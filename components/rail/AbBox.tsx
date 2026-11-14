import Link from "next/link";
import type { OfferItem } from "@/lib/offers";
import type { MoneyTarget } from "@/lib/money-pages";
import { AFFILIATE_REL } from "@/lib/affiliate";
import { AB_ARMS, altLinkText, type AbArm, type AbCard, type AbNumber } from "@/lib/ad-ab";
import { Pixels, PrTag } from "@/components/rail/parts";

/**
 * 得のカードの A/B の囲み（lib/ad-ab.ts。台帳 W41）。arm 1「結果を先に見せる」と arm 2「比べて選ぶ」を両方 HTML に入れ、
 * <html data-abc> で片方だけ見せる（app/globals.css の .abx-arm-1 / .abx-arm-2。描画前に決まるので画面がずれない）。
 * 1つの囲みにボタンは1つ。ほかの提携先とサイト内の案内は、ボタンの下の小さな文字のリンクの1行。表示は右上の「PR」の札だけ（台帳 W40）。
 * クリックは囲みの data-aff-pos と、押したリンクの data-ab-arm（components/AffClickTracker.tsx）、表示は components/ReadingBeacon.tsx で数える
 */
export default function AbBox({
  card,
  item,
  rest = [],
  pos,
  internal,
  pixels = [],
  className = "",
  id,
}: {
  card: AbCard;
  item: OfferItem;
  rest?: OfferItem[];
  pos: string;
  internal?: MoneyTarget;
  pixels?: string[];
  className?: string;
  id?: string;
}) {
  const tool = card.tool ?? internal;
  return (
    <aside id={id} data-aff-pos={pos} data-ad-ab="" data-ab-box={card.kind} aria-label="PR：広告" className={`ad-box abx relative overflow-hidden ${className}`}>
      {AB_ARMS.map((arm) => (
        <div key={arm} data-ab-arm={arm} className={`abx-arm abx-arm-${arm}`}>
          <div className="abx-top">
            <p className="abx-who">{card.who}</p>
            <PrTag />
          </div>
          {arm === "1" ? <Result card={card} /> : <Compare card={card} />}
          <a href={item.url} target="_blank" rel={AFFILIATE_REL} data-aff-rank={1} className="pr-cta abx-cta">
            {card.cta}
          </a>
          <Links arm={arm} tool={tool} rest={rest} first={item} />
          <p className="abx-note text-note">{arm === "1" ? card.note.arm1 : card.note.arm2}</p>
        </div>
      ))}
      <Pixels pixels={pixels} />
    </aside>
  );
}

function Num({ n, big = false }: { n: AbNumber; big?: boolean }) {
  return (
    <span className={`abx-num ${big ? "abx-num-big" : ""}`}>
      {n.pre && <span className="abx-unit">{n.pre}</span>}
      <span className="abx-digits">{n.num}</span>
      {n.unit && <span className="abx-unit">{n.unit}</span>}
    </span>
  );
}

function Result({ card }: { card: AbCard }) {
  const { number, after, line } = card.result;
  return (
    <div className="abx-result">
      <p className="abx-big">
        {line && <span className="abx-label">{line}</span>}
        <Num n={number} big />
        {card.kind !== "generic" && after && <span className="abx-after">{after}</span>}
      </p>
      {card.kind === "generic" && after && <p className="abx-sub">{after}</p>}
      {card.result.line2 && <p className="abx-sub">{card.result.line2}</p>}
    </div>
  );
}

function Compare({ card }: { card: AbCard }) {
  const { lead, bars, chips } = card.compare;
  return (
    <div className="abx-compare">
      {lead && <p className="abx-lead">{lead}</p>}
      {bars ? (
        <div className="abx-bars">
          {bars.map((bar) => (
            <div key={bar.label} className="abx-bar">
              <div className="abx-bar-row">
                <span className="abx-bar-label">{bar.label}</span>
                <span className={`abx-bar-value ${bar.accent ? "is-accent" : ""}`}>{bar.value}</span>
              </div>
              <div className="abx-track" aria-hidden="true">
                <div className={`abx-fill ${bar.accent ? "is-accent" : ""}`} style={{ width: `${Math.max(3, Math.min(100, bar.ratio * 100))}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className={`abx-chips abx-chips-${Math.min(3, chips?.length ?? 1)}`}>
          {(chips ?? []).map((chip) => (
            <div key={`${chip.label}-${chip.value}`} className="abx-chip">
              <span className="abx-chip-label">{chip.label}</span>
              <span className="abx-chip-value">{chip.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** ボタンの下の小さなリンクの1行: サイト内の案内・ほかの提携先（rel=sponsored と data-aff-rank はそのまま） */
function Links({ arm, tool, rest, first }: { arm: AbArm; tool?: MoneyTarget; rest: OfferItem[]; first: OfferItem }) {
  if (!tool && rest.length === 0) return null;
  // 1行（タップの高さ 44px）に収める。言葉は lib/ad-ab.ts の altLinkText（「au PAYでも探せる」「ITものづくり教室なら：LITALICOワンダー」）。
  // 言葉の作れない提携先・1行に収まらない提携先は出さない
  let room = 24 - (tool?.label.length ?? 0);
  const shown: { item: OfferItem; text: string }[] = [];
  for (const other of rest.slice(0, tool ? 1 : 2)) {
    const text = altLinkText(other, first);
    if (!text || text.length > room) continue;
    shown.push({ item: other, text });
    room -= text.length;
  }
  return (
    <p className="abx-links">
      {tool && (
        <Link href={tool.href} data-money-link="" className="abx-link">
          {tool.label}
        </Link>
      )}
      {shown.map(({ item: other, text }, index) => (
        <a key={`${arm}-${other.key}`} href={other.url} target="_blank" rel={AFFILIATE_REL} data-aff-rank={index + 2} className="abx-link">
          {text}
        </a>
      ))}
    </p>
  );
}
