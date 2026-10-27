import type { Company } from "@/lib/companies";

type Props = {
  company: Company;
  /** 表示サイズ（px） */
  size?: number;
  /** 企業名も並べて出す */
  withName?: boolean;
  className?: string;
};

/**
 * 企業の色見本。ロゴは使わず、企業ごとの色と頭文字だけで見分けられるようにする。
 * 名前を並べる場合、色見本は装飾なので読み上げない。
 */
export default function CompanyMark({ company, size = 20, withName, className = "" }: Props) {
  const swatch = (
    <span
      aria-hidden={withName ? true : undefined}
      aria-label={withName ? undefined : company.name}
      role={withName ? undefined : "img"}
      // 企業の色見本（ロゴ扱い）。文字サイズ・コントラストのルールの対象外（docs/typography.md）
      data-decorative=""
      className="index-num inline-grid shrink-0 place-items-center rounded-[6px] font-semibold leading-none text-white"
      style={{
        width: size,
        height: size,
        background: company.color,
        fontSize: Math.round(size * (company.mark.length > 1 ? 0.42 : 0.55)),
      }}
    >
      {company.mark}
    </span>
  );

  if (!withName) return <span className={className}>{swatch}</span>;

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      {swatch}
      <span className="font-bold text-ink">{company.name}</span>
    </span>
  );
}
