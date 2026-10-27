import type { Bundle, StoryItem } from "@/components/story/SwipeDeck";
import { coverPath, getAllArticles, type ArticleSummary } from "@/lib/articles";
import { companyOf } from "@/lib/companies";
import { easyGist, pickGeneral } from "@/lib/general";
import { freeLabel, japanLabel, usability, USABILITY_LABEL } from "@/lib/verdict";

function toItem(a: ArticleSummary): StoryItem {
  const c = companyOf(a);
  const v = a.verdict ?? null;
  return {
    slug: a.slug,
    title: a.title,
    gist: easyGist(a),
    highlights: a.highlights.slice(0, 3),
    // 画像の無い web 記事は、企業色入りの独自カバーで代用する
    image: a.thumbnail || coverPath(a) || "",
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

/** トップ上段の「ストーリーの丸」の束。3本未満の束は出さない */
export function getStoryBundles(): Bundle[] {
  const ai = getAllArticles().filter((a) => a.genreSlug === "ai" && a.type !== "roundup" && a.hasEasy);
  const recent = ai.slice(0, 60);
  const byCompany = (slug: string) => recent.filter((a) => companyOf(a).slug === slug).slice(0, 6);
  return [
    { key: "today", label: "注目の7本", items: pickGeneral(ai, 7).map(toItem) },
    { key: "go", label: "今すぐ使える", items: recent.filter((a) => a.verdict && usability(a.verdict) === "go").slice(0, 7).map(toItem) },
    { key: "free", label: "無料で試せる", items: recent.filter((a) => a.verdict?.free).slice(0, 7).map(toItem) },
    { key: "openai", label: "OpenAI", items: byCompany("openai").map(toItem) },
    { key: "google", label: "Google", items: byCompany("google").map(toItem) },
    { key: "anthropic", label: "Anthropic", items: byCompany("anthropic").map(toItem) },
  ].filter((b) => b.items.length >= 3);
}
