/**
 * 記事を一歩深くする欄の形と取り出し（scripts/depth_fields.py が書く。components/DepthBoxes.tsx が描く。台帳 A66）。
 * 画面に出す前にもう一度、URL が https:// か http:// の外のページかだけを確かめる（ほかの照合は書く段で済んでいる）。
 */
import { answeredOnly } from "@/lib/nonanswer";

export type InsightItem = { text: string; source: string };
export type DeskEntry = { name: string; url: string; source?: string; howTo?: string[]; phone?: string; hours?: string; note?: string };
export type StepItem = { action: string; steps?: string[]; url?: string; source?: string };
export type Cause = { text: string; status?: "stated" | "investigating" | "background"; source: string };
export type WorryItem = { q: string; a: string; action?: string; source: string; general?: boolean; actionSource?: string; actionGeneral?: boolean };

export type GuideRow = { question: string; situation: string; recommend: string; reason: string; source: string; general?: boolean };

export type DepthHeadings = Partial<Record<"insight" | "cause" | "steps" | "desk" | "worries" | "guide", string>>;

export type DepthFields = {
  depthHeadings?: DepthHeadings;
  decisionGuide?: GuideRow[];
  insight?: InsightItem[];
  officialDesk?: DeskEntry[];
  todaySteps?: StepItem[];
  cause?: Cause | null;
  worries?: WorryItem[];
};

const okUrl = (u: unknown): u is string => typeof u === "string" && /^https?:\/\/[^\s"<>]+$/.test(u);
const str = (s: unknown): s is string => typeof s === "string" && s.trim().length > 0;

/** 記事の JSON から、画面に出せる形の欄だけを取り出す（壊れた項目は外す） */
export function depthOf(a: DepthFields) {
  const insight = (a.insight ?? []).filter((x) => str(x?.text) && okUrl(x?.source)).slice(0, 3);
  const officialDesk = (a.officialDesk ?? [])
    .filter((d) => str(d?.name) && okUrl(d?.url))
    .map((d) => ({ ...d, howTo: (d.howTo ?? []).filter(str).slice(0, 5) }))
    .slice(0, 3);
  const steps = (a.todaySteps ?? [])
    .filter((s) => str(s?.action))
    .map((s) => ({ ...s, steps: (s.steps ?? []).filter(str).slice(0, 4), url: okUrl(s.url) ? s.url : undefined }))
    .slice(0, 3);
  const cause = a.cause && str(a.cause.text) && okUrl(a.cause.source) ? a.cause : null;
  // 答えが「書かれていません」の不安は出さない（2文目以降のその文は外す。lib/nonanswer.ts。SEO A4・LLMO-A4）。2つ未満なら欄ごと出さない
  const worries = answeredOnly((a.worries ?? []).filter((w) => str(w?.q) && str(w?.a) && okUrl(w?.source)))
    .map((w) => ({ ...w, actionSource: okUrl(w.actionSource) ? w.actionSource : undefined }))
    .slice(0, 5);
  // 判断ガイド: 問いごとにまとめる（同じ問いの状況違いの行を並べる）
  const guide: { question: string; rows: GuideRow[] }[] = [];
  for (const r of (a.decisionGuide ?? []).filter((x) => str(x?.question) && str(x?.situation) && str(x?.recommend) && str(x?.reason) && okUrl(x?.source)).slice(0, 6)) {
    const group = guide.find((g) => g.question === r.question);
    if (group) group.rows.push(r);
    else guide.push({ question: r.question, rows: [r] });
  }
  const headings: DepthHeadings = {};
  for (const [k, v] of Object.entries(a.depthHeadings ?? {})) {
    // 28字まで・「｜」なし（scripts/depth_fields.py と同じ決まり。2026-11-09 オーナー）
    if (str(v) && v.length <= 28 && !/[｜|]/.test(v)) headings[k as keyof DepthHeadings] = v;
  }
  return {
    headings,
    guide,
    insight,
    officialDesk,
    todaySteps: steps.length >= 2 ? steps : [],
    cause,
    worries: worries.length >= 2 ? worries : [],
  };
}

/** 出典の表示名（ホスト名。www. は外す。docomo.ne.jp のように短く） */
export function sourceLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "公式ページ";
  }
}
