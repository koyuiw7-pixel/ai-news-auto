import fs from "node:fs";
import path from "node:path";

export type Cta = {
  eyebrow?: string;
  title: string;
  body?: string;
  buttonLabel: string;
  url: string;
  note?: string;
  /**
   * アフィリエイトIDが設定済みか。
   * false のときは計測パラメータを外した公式URLへの通常リンクとして扱い、
   * PR表記と rel="sponsored" を付けない（未提携の状態で報酬リンクを装わないため）。
   */
  isAffiliate: boolean;
};

export type CtaSlot = "primary" | "inline" | "secondary";

type GenreCtas = Partial<Record<CtaSlot, Cta>>;

const CONFIG_PATH = path.join(process.cwd(), "monetization.json");

/** 未設定のプレースホルダを本番に出さないためのガード */
function isPlaceholder(url: string): boolean {
  return (
    !url ||
    url.includes("YOUR_ID") ||
    url.includes("your_aff_link") ||
    url.includes("example.com")
  );
}

type RawCta = Omit<Cta, "isAffiliate">;

function isRawCta(value: unknown): value is RawCta {
  if (typeof value !== "object" || value === null) return false;
  const c = value as Record<string, unknown>;
  return (
    typeof c.title === "string" &&
    typeof c.buttonLabel === "string" &&
    typeof c.url === "string"
  );
}

/** 未設定のまま公開されても壊れないよう、計測パラメータを落として素のURLにする */
function stripTracking(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return url.split("?")[0];
  }
}

let cache: Record<string, GenreCtas> | null = null;

function load(): Record<string, GenreCtas> {
  if (cache) return cache;

  const result: Record<string, GenreCtas> = {};
  try {
    const raw: unknown = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
    if (typeof raw === "object" && raw !== null) {
      for (const [genre, slots] of Object.entries(raw)) {
        if (genre.startsWith("_")) continue; // _README などのメモ
        if (typeof slots !== "object" || slots === null) continue;

        const collected: GenreCtas = {};
        for (const [slot, cta] of Object.entries(slots)) {
          if (!isRawCta(cta)) continue;
          const pending = isPlaceholder(cta.url);
          collected[slot as CtaSlot] = {
            ...cta,
            url: pending ? stripTracking(cta.url) : cta.url,
            isAffiliate: !pending,
          };
        }
        result[genre] = collected;
      }
    }
  } catch {
    // 設定が無い/壊れていても本文表示は止めない
  }

  cache = result;
  return result;
}

export function getCta(genreSlug: string, slot: CtaSlot): Cta | null {
  const cta = load()[genreSlug]?.[slot] ?? null;
  // 提携前（計測IDなし）の枠は出さない。報酬の出ない他社への誘導で、
  // 読者の注意と回遊を外へ流すだけになるため
  return cta?.isAffiliate ? cta : null;
}

/** 有効なCTAが1つでもあるか（無ければ導線UIごと隠す） */
export function hasAnyCta(): boolean {
  return Object.values(load()).some((slots) => Object.keys(slots).length > 0);
}

/**
 * 実際に成果報酬が発生するリンクを1本でも掲載しているか。
 *
 * ASP未提携のうちに「アフィリエイトプログラムに参加しています」と書くのは
 * 事実と異なるため、規約系ページの文言をこの結果で切り替える。
 */
export function hasActiveAffiliate(): boolean {
  const viaCta = Object.values(load()).some((slots) =>
    Object.values(slots).some((cta) => cta?.isAffiliate),
  );
  if (viaCta) return true;

  // 記事内リンク側（affiliate_links.json）も見る
  try {
    const raw: unknown = JSON.parse(
      fs.readFileSync(path.join(process.cwd(), "affiliate_links.json"), "utf8"),
    );
    if (typeof raw !== "object" || raw === null) return false;
    return Object.entries(raw).some(([name, value]) => {
      if (name.startsWith("_")) return false;
      const url = typeof value === "string" ? value : (value as { url?: string })?.url;
      return typeof url === "string" && !isPlaceholder(url);
    });
  } catch {
    return false;
  }
}
