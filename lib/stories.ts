import type { Bundle, StoryItem } from "@/components/story/SwipeDeck";
import { coverPath, getAllArticles, type ArticleSummary } from "@/lib/articles";
import { COMPANIES, companyOf } from "@/lib/companies";
import { easyGist, pickGeneral } from "@/lib/general";
import { BROAD_SECTIONS } from "@/lib/sections";
import { freeLabel, japanLabel, usability, USABILITY_LABEL } from "@/lib/verdict";

const DAY_MS = 86_400_000;
/** 束に入れる記事の新しさ（最新記事から何日以内か） */
const WINDOW_DAYS = 7;
/** これ未満の束は出さない（スカスカの丸は意味がない） */
const MIN_ITEMS = 3;
const MAX_ITEMS = 7;
/** PC の1列（1240px）にちょうど収まる数 */
const MAX_BUNDLES = 12;

/** 幅広い話題の丸の名前（丸の下は短くないと切れる） */
const GENRE_LABEL: Record<string, string> = {
  business: "ビジネス",
  "tech-gadget": "ガジェット",
  lifestyle: "暮らし",
  entertainment: "エンタメ",
  sports: "スポーツ",
  science: "科学・宇宙",
  public: "社会・行政",
};

const WORK =
  /業務|仕事|効率|会議|議事録|Excel|Word|PowerPoint|Office|Microsoft 365|資料|メール|Slack|Notion|営業|人事|採用|マーケ|ビジネスパーソン|中小企業|DX/;
/** 画像・動画「を作る」話だけ（「解説動画を公開」のような記事を混ぜない）。見出しで判定する */
const CREATIVE = /(画像|動画|映像|イラスト|音楽)を?(生成|編集|作成|制作)|Sora|Veo|Imagen|Nano Banana|Midjourney|Firefly/;
const DEV = /開発者|エンジニア|開発ツール|API|SDK|GitHub|Codex|コーディング|プログラ/;
const AGENT = /エージェント|Agent/i;

function textOf(a: ArticleSummary): string {
  return `${a.title} ${a.tags.join(" ")} ${a.verdict?.audience ?? ""}`;
}

function toItem(a: ArticleSummary): StoryItem {
  const ai = a.genreSlug === "ai";
  const c = companyOf(a);
  const v = a.verdict ?? null;
  return {
    slug: a.slug,
    title: a.title,
    gist: easyGist(a),
    highlights: a.highlights.slice(0, 3),
    // 画像の無い web 記事は、企業色入りの独自カバーで代用する
    image: a.thumbnail || coverPath(a) || "",
    // AI以外の話題は企業ではなくジャンル名を出す
    company: ai ? c.name : GENRE_LABEL[a.genreSlug] ?? a.genre,
    color: ai ? c.color : "#62625d",
    at: a.generatedAt,
    usable: v ? usability(v) : null,
    usableLabel: v ? USABILITY_LABEL[usability(v)] : null,
    japan: v ? japanLabel(v) : null,
    free: v ? freeLabel(v.free) : null,
    price: v?.price ?? null,
  };
}

/** theme は用途別の束（中身が重なりやすいので、ほぼ同じなら出さない）。企業・ジャンルは道しるべなので常に出す */
type Draft = { key: string; label: string; items: ArticleSummary[]; theme?: boolean };

/** 見た目が同じになる画像を見分けるキー（独自カバーは企業色が同じなら見分けがつかない） */
function lookKey(a: ArticleSummary): string {
  if (a.thumbnail) return a.thumbnail.replace(/(maxres|hq|mq|sd)default/, "");
  return a.genreSlug === "ai" ? `cover:${companyOf(a).slug}` : `cover:${a.genreSlug}`;
}

/**
 * 丸ごとに違う表紙を選ぶ。同じ記事・同じ見た目（同じ企業色の独自カバー）は使い回さず、
 * 写真のある記事を優先する。どうしても無ければ、まだ表紙にしていない記事で妥協する。
 */
function pickCovers(drafts: Draft[]): (ArticleSummary | undefined)[] {
  const usedSlug = new Set<string>();
  const usedLook = new Set<string>();
  return drafts.map((d) => {
    const fresh = d.items.filter((a) => !usedSlug.has(a.slug));
    const pick =
      fresh.find((a) => a.thumbnail && !usedLook.has(lookKey(a))) ??
      fresh.find((a) => !usedLook.has(lookKey(a))) ??
      fresh[0] ??
      d.items[0];
    if (pick) {
      usedSlug.add(pick.slug);
      usedLook.add(lookKey(pick));
    }
    return pick;
  });
}

/** 先に出た束とほぼ同じ中身の束は、丸を増やすだけなので出さない */
function isNearDuplicate(items: ArticleSummary[], earlier: Draft[]): boolean {
  const slugs = new Set(items.map((a) => a.slug));
  return earlier.some((d) => {
    const shared = d.items.filter((a) => slugs.has(a.slug)).length;
    return shared / Math.min(slugs.size, d.items.length) >= 0.75;
  });
}

/**
 * トップ上段の「ストーリーの丸」の束。
 * 役に立つ順（一般向けの注目 → 使える・無料 → 用途別 → 企業別 → AI以外の話題）に並べ、
 * 直近7日で3本以上ある束だけを出す。
 */
export function getStoryBundles(): Bundle[] {
  const all = getAllArticles().filter((a) => a.type !== "roundup" && a.hasEasy);
  // ビルド時刻ではなく最新記事を基準にする（更新が止まっても丸が全部消えないように）
  const latest = Math.max(0, ...all.map((a) => Date.parse(a.generatedAt) || 0));
  const recent = all.filter((a) => latest - (Date.parse(a.generatedAt) || 0) < WINDOW_DAYS * DAY_MS);
  const ai = recent.filter((a) => a.genreSlug === "ai");
  // 用途別の束も、一般の人に関係ある話を優先して選ぶ（表示は新しい順）
  const ofAi = (test: (a: ArticleSummary) => boolean) => pickGeneral(ai.filter(test), MAX_ITEMS, 60);

  // 企業別は、直近の記事が多い企業から
  const companies = COMPANIES.map((c) => ({ c, items: ai.filter((a) => companyOf(a).slug === c.slug) }))
    .filter((x) => x.items.length >= MIN_ITEMS)
    .sort((x, y) => y.items.length - x.items.length);

  const genres = BROAD_SECTIONS.map((s) => ({ s, items: recent.filter((a) => a.genreSlug === s.slug) }))
    .filter((x) => x.items.length >= MIN_ITEMS)
    .sort((x, y) => y.items.length - x.items.length);

  const byGenre = genres.map(({ s, items }) => ({
    key: `g-${s.slug}`,
    label: GENRE_LABEL[s.slug] ?? s.label,
    items: items.slice(0, MAX_ITEMS),
  }));

  const candidates: Draft[] = [
    { key: "today", label: "注目の7本", items: pickGeneral(ai, MAX_ITEMS) },
    // 「使える」は注目と中身が重ならないよう、新しい順のまま出す
    {
      key: "go",
      label: "今すぐ使える",
      items: ai.filter((a) => a.verdict && usability(a.verdict) === "go").slice(0, MAX_ITEMS),
      theme: true,
    },
    { key: "free", label: "無料で試せる", items: ofAi((a) => a.verdict?.free === true), theme: true },
    { key: "work", label: "仕事で使える", items: ofAi((a) => WORK.test(textOf(a))), theme: true },
    { key: "creative", label: "画像・動画", items: ofAi((a) => CREATIVE.test(a.title)), theme: true },
    {
      key: "followup",
      label: "続報あり",
      items: all
        .filter((a) => a.updatedAt && latest - Date.parse(a.updatedAt) < WINDOW_DAYS * DAY_MS)
        .sort((x, y) => Date.parse(y.updatedAt!) - Date.parse(x.updatedAt!))
        .slice(0, MAX_ITEMS),
    },
    ...companies.slice(0, 5).map(({ c, items }) => ({ key: c.slug, label: c.name, items: items.slice(0, MAX_ITEMS) })),
    // AI以外の話題は多い順に3つまで先に出し、残りは枠が余ったときだけ
    ...byGenre.slice(0, 3),
    { key: "dev", label: "開発者向け", items: ofAi((a) => DEV.test(textOf(a))), theme: true },
    { key: "agent", label: "AIエージェント", items: ofAi((a) => AGENT.test(textOf(a))), theme: true },
    ...byGenre.slice(3),
  ];

  const drafts: Draft[] = [];
  for (const d of candidates) {
    if (drafts.length >= MAX_BUNDLES) break;
    if (d.items.length < MIN_ITEMS) continue;
    if (d.theme && isNearDuplicate(d.items, drafts)) continue;
    drafts.push(d);
  }

  const covers = pickCovers(drafts);
  return drafts.map((d, i) => {
    const cover = covers[i];
    return {
      key: d.key,
      label: d.label,
      cover: cover ? toItem(cover).image : "",
      items: d.items.map(toItem),
    };
  });
}
