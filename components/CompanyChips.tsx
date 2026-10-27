import Link from "next/link";
import CompanyMark from "@/components/CompanyMark";
import type { Company } from "@/lib/companies";

type Props = {
  companies: { company: Company; count: number }[];
  /** 選択中の企業（企業別ページで使う） */
  active?: string;
};

/** 企業での絞り込み。チップは本文の左端に揃え、はみ出す分は横にスクロールする */
export default function CompanyChips({ companies, active }: Props) {
  return (
    <div className="border-b border-line bg-paper">
      <nav
        aria-label="企業で絞り込む"
        className="mx-auto flex max-w-[1240px] gap-1.5 overflow-x-auto px-5 py-3 [scrollbar-width:none] sm:px-8"
      >
        <Chip href="/" active={!active}>
          すべて
        </Chip>
        {companies.map(({ company, count }) => (
          <Chip key={company.slug} href={`/companies/${company.slug}`} active={active === company.slug}>
            <CompanyMark company={company} size={14} />
            {company.name}
            <span className="index-num text-meta text-muted">{count}</span>
          </Chip>
        ))}
      </nav>
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
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-meta font-bold transition-colors ${
        active
          ? "border-ink bg-ink text-paper [&_.text-muted]:text-paper/70"
          : "border-line text-ink-soft hover:border-ink hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}
