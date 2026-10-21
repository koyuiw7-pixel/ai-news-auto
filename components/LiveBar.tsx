import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import RelTime from "@/components/RelTime";
import type { Company } from "@/lib/companies";

type Props = {
  /** 最後に記事を追加した日時（ISO） */
  updatedAt?: string;
  /** 直近24時間に追加した本数（ビルド時点） */
  recentCount: number;
  /** 直近7日間に追加した本数。24時間で0本のときに代わりに出す */
  weekCount: number;
  companies: { company: Company; count: number }[];
  /** 選択中の企業（企業別ページで使う） */
  active?: string;
};

/**
 * 「いま動いている」ことを示す帯と、企業での絞り込み。
 * 流れる文字（ティッカー）は読みにくく目が疲れるのでやめ、
 * 最終更新の経過時間を止まった状態で見せる。
 */
export default function LiveBar({ updatedAt, recentCount, weekCount, companies, active }: Props) {
  return (
    <div className="border-b border-line bg-paper">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-3 px-5 py-3 sm:px-8 md:flex-row md:items-center md:gap-6">
        <p className="flex shrink-0 items-center gap-2.5 text-[12px]">
          <span className="relative flex size-2" aria-hidden>
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-live opacity-60 motion-reduce:hidden" />
            <span className="relative inline-flex size-2 rounded-full bg-live" />
          </span>
          <span className="font-bold tracking-wider text-live">LIVE</span>
          {updatedAt && (
            <span className="text-muted">
              最終更新 <RelTime iso={updatedAt} className="index-num font-semibold text-ink" />
            </span>
          )}
          <span className="index-num text-muted">
            ・{recentCount > 0 ? `24時間で${recentCount}本` : `今週${weekCount}本`}
          </span>
        </p>

        <nav
          aria-label="企業で絞り込む"
          className="-mx-5 flex min-w-0 gap-1.5 overflow-x-auto px-5 [scrollbar-width:none] sm:-mx-8 sm:px-8 md:mx-0 md:px-0"
        >
          <Chip href="/" active={!active}>
            すべて
          </Chip>
          {companies.map(({ company, count }) => (
            <Chip key={company.slug} href={`/companies/${company.slug}`} active={active === company.slug}>
              <CompanyMark company={company} size={14} />
              {company.name}
              <span className="index-num text-[10.5px] text-muted">{count}</span>
            </Chip>
          ))}
        </nav>
      </div>
    </div>
  );
}

function Chip({
  href,
  active,
  children,
}: {
  href: string;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12.5px] font-bold transition-colors ${
        active
          ? "border-ink bg-ink text-paper [&_.text-muted]:text-paper/70"
          : "border-line text-ink-soft hover:border-ink hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}
