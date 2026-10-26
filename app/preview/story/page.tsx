import type { Metadata } from "next";
import HomePage from "@/app/page";
import type { StoryItem } from "@/components/story/StoryDeck";
import StoryRail, { type Bundle } from "@/components/story/SwipeDeck";
import { getAllArticles, type Article } from "@/lib/articles";
import { companyOf } from "@/lib/companies";
import { easyGist, pickGeneral } from "@/lib/general";
import { freeLabel, japanLabel, usability, USABILITY_LABEL } from "@/lib/verdict";

export const metadata: Metadata = {
  title: "ストーリー試作",
  robots: { index: false, follow: false },
};

function toItem(a: Article): StoryItem {
  const c = companyOf(a);
  const v = a.verdict ?? null;
  return {
    slug: a.slug,
    title: a.title,
    gist: easyGist(a),
    highlights: a.highlights.slice(0, 3),
    image: a.thumbnail,
    company: c.name,
    color: c.color,
    at: a.generatedAt,
    usable: v ? usability(v) : null,
    usableLabel: v ? USABILITY_LABEL[usability(v)] : null,
    japan: v ? japanLabel(v) : null,
    free: v ? freeLabel(v.free) : null,
    price: v?.price ?? null,
  };
}

/** トップの上段に「ストーリーの丸」を足した試作（下は今のトップのまま） */
export default function StoryPreviewPage() {
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai" && a.type !== "roundup" && a.easy);
  const recent = ai.slice(0, 60);
  const byCompany = (slug: string) => recent.filter((a) => companyOf(a).slug === slug).slice(0, 6);
  const bundles: Bundle[] = [
    { key: "today", label: "今日の7本", items: pickGeneral(ai, 7).map(toItem) },
    { key: "go", label: "今すぐ使える", items: recent.filter((a) => a.verdict && usability(a.verdict) === "go").slice(0, 7).map(toItem) },
    { key: "free", label: "無料で試せる", items: recent.filter((a) => a.verdict?.free).slice(0, 7).map(toItem) },
    { key: "openai", label: "OpenAI", items: byCompany("openai").map(toItem) },
    { key: "google", label: "Google", items: byCompany("google").map(toItem) },
    { key: "anthropic", label: "Anthropic", items: byCompany("anthropic").map(toItem) },
  ].filter((b) => b.items.length >= 3);

  return (
    <>
      <StoryRail bundles={bundles} />
      <HomePage />
    </>
  );
}
