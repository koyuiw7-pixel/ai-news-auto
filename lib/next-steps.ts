import data from "@/content/next_steps.json";

/** よく読まれる記事の「あなたは対象？」と「次にやること」（content/next_steps.json。2026-11-10 オーナー承認） */
export type CheckItem = { text: string; slug?: string; href?: string; link?: string };
export type NextStepsEntry = {
  check?: { title: string; note?: string; items: CheckItem[]; branch?: { text: string; slug?: string; href?: string } };
  next?: { step: string; slug: string }[];
};

const ARTICLES = (data as { articles: Record<string, NextStepsEntry> }).articles;

export function nextStepsFor(slug: string): NextStepsEntry | undefined {
  return ARTICLES[slug];
}

export function allNextSteps(): Record<string, NextStepsEntry> {
  return ARTICLES;
}
