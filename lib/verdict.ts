import type { ArticleSummary } from "@/lib/articles";

/**
 * 「使えるかどうか」の判定。記事生成時に Gemini が本文の料金・提供状況から付ける。
 * サイソクの軸は「速さ」だけでなく「今それを使えるかを最速で判定する」こと。
 */
export type Verdict = {
  status: "available" | "limited" | "soon" | "demo";
  japan: "ok" | "partial" | "no" | "unknown";
  price: string;
  free: boolean | null;
  audience: string;
  take: string;
  /** 判定した日時。無ければ記事の生成日時 */
  judgedAt?: string;
};

/** 一覧で出す3段階。迷わないよう「使える／一部／まだ」の3つだけにする */
export type Usability = "go" | "partial" | "wait";

export function usability(verdict: Verdict): Usability {
  if (verdict.status === "available" && verdict.japan !== "no") return "go";
  if (verdict.status === "available" || verdict.status === "limited") return "partial";
  return "wait";
}

export const USABILITY_LABEL: Record<Usability, string> = {
  go: "使える",
  partial: "一部",
  wait: "まだ",
};

export const STATUS_LABEL: Record<Verdict["status"], string> = {
  available: "今すぐ使える",
  limited: "一部で提供中",
  soon: "提供はこれから",
  demo: "研究・デモ段階",
};

export const JAPAN_LABEL: Record<Verdict["japan"], string> = {
  ok: "利用できる",
  partial: "条件付きで利用可",
  no: "日本では未提供",
  unknown: "記載なし",
};

/** 提供前の製品で「日本では未提供」と出すと日本だけ除外されたように読めるので「提供前」にする */
export function japanLabel(verdict: Verdict): string {
  if (verdict.status === "soon" || verdict.status === "demo") {
    return verdict.japan === "ok" ? "日本でも提供予定" : "提供前";
  }
  return JAPAN_LABEL[verdict.japan];
}

export function freeLabel(free: boolean | null): string {
  if (free === true) return "無料で試せる";
  if (free === false) return "有料のみ";
  return "記載なし";
}

/** まとめ記事や判定のない古い記事には出さない */
export function verdictOf(article: ArticleSummary): Verdict | undefined {
  if (article.type === "roundup") return undefined;
  return article.verdict ?? undefined;
}
