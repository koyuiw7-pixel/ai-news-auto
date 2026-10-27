import Link from "next/link";
import { pageHref } from "@/lib/paginate";

/** 一覧のページ送り。前後と、今のページの周りの番号だけ出す */
export default function Pagination({ base, page, totalPages }: { base: string; page: number; totalPages: number }) {
  if (totalPages <= 1) return null;
  const pages = [...new Set([1, page - 2, page - 1, page, page + 1, page + 2, totalPages])]
    .filter((n) => n >= 1 && n <= totalPages)
    .sort((a, b) => a - b);
  const item = "flex h-10 min-w-10 items-center justify-center rounded-md border px-3 text-meta font-bold";

  return (
    <nav aria-label="ページ送り" className="mt-12 flex flex-wrap items-center justify-center gap-2">
      {page > 1 && (
        <Link href={pageHref(base, page - 1)} rel="prev" className={`${item} border-line text-ink-soft hover:border-ink`}>
          前へ
        </Link>
      )}
      {pages.map((n, i) => (
        <span key={n} className="flex items-center gap-2">
          {i > 0 && n - pages[i - 1] > 1 && <span className="text-muted">…</span>}
          {n === page ? (
            <span aria-current="page" className={`${item} border-ink bg-ink text-paper`}>
              {n}
            </span>
          ) : (
            <Link href={pageHref(base, n)} className={`${item} border-line text-ink-soft hover:border-ink`}>
              {n}
            </Link>
          )}
        </span>
      ))}
      {page < totalPages && (
        <Link href={pageHref(base, page + 1)} rel="next" className={`${item} border-line text-ink-soft hover:border-ink`}>
          次へ
        </Link>
      )}
    </nav>
  );
}
