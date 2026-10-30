"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { difyDecisionHref } from "@/lib/a8-attribution";
import { GUIDE_PATH } from "@/lib/revenue-funnel";

/** 共通フッターでも、現在表示している2記事だけを固定コードで引き継ぐ。 */
export default function DifyDecisionLink({ children, className }: { children: ReactNode; className?: string }) {
  const pathname = usePathname();
  return <Link href={difyDecisionHref(pathname ?? "", GUIDE_PATH)} className={className}>{children}</Link>;
}
