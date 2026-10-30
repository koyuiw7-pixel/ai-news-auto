"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { installDifyA8Attribution } from "@/lib/a8-attribution";

/** SSRの広告URLを保持し、許可された環境のDify比較だけで公式の分類値を追加する。 */
export default function DifyA8Attribution() {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  useEffect(() => {
    if (!pathname) return;
    // query変更・戻る操作でもcleanupで元へ戻してから再計算する。保存領域・Cookieは使わない。
    return installDifyA8Attribution(pathname, search, document, navigator, location.origin);
  }, [pathname, search]);
  return null;
}
