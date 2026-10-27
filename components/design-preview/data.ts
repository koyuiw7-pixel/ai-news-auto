/** 配色案の比較ページ（/design-preview）で使う型と、3案の色・形のトークン */

export type Japan = "ok" | "partial" | "no" | "unknown";

export type PreviewModel = {
  id: string;
  product: string;
  companyName: string;
  mark: string;
  color: string;
  input: number;
  output: number;
  japan: Japan;
  productSlug: string | null;
};

export type PreviewData = {
  models: PreviewModel[];
  updatedAt: string;
  modelCount: number;
  articleCount: number;
  article: {
    slug: string;
    title: string;
    description: string;
    publishedAt: string;
    source: string;
    companyName: string;
    companyColor: string;
    speed: string | null;
    cover: string;
  };
  roundupCount: number;
  product: {
    slug: string;
    name: string;
    category: string;
    companyName: string;
    mark: string;
    color: string;
    overview: string;
    articleCount: number;
    updatedAt: string;
    input: number | null;
    output: number | null;
    japan: Japan;
  } | null;
};

export type DirKey = "a" | "b" | "c";
export type Mode = "light" | "dark";

/** 色のトークン（ライト・ダークで差し替える） */
export type ColorTokens = {
  bg: string;
  surface: string;
  "surface-2": string;
  ink: string;
  "ink-soft": string;
  muted: string;
  line: string;
  "line-strong": string;
  /** 文字・線に使うアクセント（背景に対し 4.5:1 以上） */
  accent: string;
  /** 面・棒グラフに使うアクセント */
  "accent-fill": string;
  /** accent-fill の上の文字 */
  "accent-ink": string;
  "accent-soft": string;
  /** 速報ラベル */
  live: string;
  "live-ink": string;
  positive: string;
  "positive-soft": string;
  caution: string;
  "caution-soft": string;
  /** 最安以外の棒 */
  bar: string;
  /** ヘッダーの帯 */
  mast: string;
  "mast-ink": string;
  "mast-muted": string;
};

/** 形のトークン（ライト・ダーク共通） */
export type ShapeTokens = {
  "radius-sm": string;
  "radius-md": string;
  "radius-lg": string;
  shadow: string;
  "shadow-lift": string;
  /** 区切り線の太さ（見出しの上など） */
  rule: string;
  /** 数字の書体 */
  "font-num": string;
};

export type Direction = {
  key: DirKey;
  label: string;
  name: string;
  /** スマホのタブ用の短い名前 */
  short: string;
  concept: string;
  /** アクセントの使いどころ */
  accentUse: string;
  shape: ShapeTokens;
  light: ColorTokens;
  dark: ColorTokens;
};

const SANS = "var(--font-noto), 'Hiragino Sans', sans-serif";
const MONO = "var(--font-martian), ui-monospace, 'SF Mono', Menlo, monospace";

export const DIRECTIONS: Direction[] = [
  {
    key: "a",
    label: "A",
    name: "報道ネイビー×速報レッド",
    short: "ネイビー",
    concept: "濃紺の帯と1pxの罫線で、報道の正確さを出す。赤は「速報」と「最安」だけ。",
    accentUse: "赤＝速報ラベル・最安の棒と数字・選択中の下線",
    shape: {
      "radius-sm": "3px",
      "radius-md": "6px",
      "radius-lg": "8px",
      shadow: "0 1px 2px rgb(11 26 51 / 0.06), 0 0 0 1px rgb(11 26 51 / 0.05)",
      "shadow-lift": "0 14px 28px -14px rgb(11 26 51 / 0.32), 0 0 0 1px rgb(11 26 51 / 0.07)",
      rule: "1px",
      "font-num": SANS,
    },
    light: {
      bg: "#F3F5F8",
      surface: "#FFFFFF",
      "surface-2": "#E9EDF3",
      ink: "#0B1A33",
      "ink-soft": "#2B3954",
      muted: "#465268",
      line: "#DCE2EB",
      "line-strong": "#BFC8D6",
      accent: "#C8221A",
      "accent-fill": "#D42A20",
      "accent-ink": "#FFFFFF",
      "accent-soft": "#FCEBE9",
      live: "#D42A20",
      "live-ink": "#FFFFFF",
      positive: "#0B7344",
      "positive-soft": "#E3F2EA",
      caution: "#8F5600",
      "caution-soft": "#FBF0DC",
      bar: "#2C4A7E",
      mast: "#0B1F45",
      "mast-ink": "#FFFFFF",
      "mast-muted": "#B4C0D8",
    },
    dark: {
      bg: "#08101F",
      surface: "#0F1A2E",
      "surface-2": "#16233D",
      ink: "#E8EDF6",
      "ink-soft": "#C1CADB",
      muted: "#A0ACC2",
      line: "#1F2C46",
      "line-strong": "#34456A",
      accent: "#FF6A5C",
      "accent-fill": "#D9322A",
      "accent-ink": "#FFFFFF",
      "accent-soft": "#3A1717",
      live: "#D9322A",
      "live-ink": "#FFFFFF",
      positive: "#4FD18B",
      "positive-soft": "#0F2C22",
      caution: "#F2B54A",
      "caution-soft": "#2E2410",
      bar: "#5872A6",
      mast: "#0C1628",
      "mast-ink": "#FFFFFF",
      "mast-muted": "#A0ACC2",
    },
  },
  {
    key: "b",
    label: "B",
    name: "テック・エメラルド",
    short: "エメラルド",
    concept: "黒に近い墨と、ひとつのエメラルド。数字は等幅の英字書体で、計器のような精密さ。",
    accentUse: "エメラルド＝最安・選択中・稼働中の印（赤は速報だけ）",
    shape: {
      "radius-sm": "6px",
      "radius-md": "10px",
      "radius-lg": "14px",
      shadow: "0 1px 2px rgb(10 20 15 / 0.05), 0 0 0 1px rgb(10 20 15 / 0.04)",
      "shadow-lift": "0 16px 32px -16px rgb(0 70 50 / 0.30), 0 0 0 1px rgb(0 120 90 / 0.25)",
      rule: "1px",
      "font-num": MONO,
    },
    light: {
      bg: "#F5F7F6",
      surface: "#FFFFFF",
      "surface-2": "#ECF0EE",
      ink: "#0B0F0D",
      "ink-soft": "#2A302D",
      muted: "#4A524E",
      line: "#E0E5E2",
      "line-strong": "#C5CDC8",
      accent: "#00785A",
      "accent-fill": "#00805F",
      "accent-ink": "#FFFFFF",
      "accent-soft": "#E1F3EC",
      live: "#D42A20",
      "live-ink": "#FFFFFF",
      positive: "#00704F",
      "positive-soft": "#E1F3EC",
      caution: "#8F5600",
      "caution-soft": "#FBF0DC",
      bar: "#AEB8B3",
      mast: "#FFFFFF",
      "mast-ink": "#0B0F0D",
      "mast-muted": "#4A524E",
    },
    dark: {
      bg: "#0A0C0B",
      surface: "#111513",
      "surface-2": "#171C19",
      ink: "#E6EBE8",
      "ink-soft": "#BFC7C3",
      muted: "#9AA49F",
      line: "#1F2622",
      "line-strong": "#323C37",
      accent: "#34CF98",
      "accent-fill": "#2EBF8B",
      "accent-ink": "#03130D",
      "accent-soft": "#0E2A20",
      live: "#D9322A",
      "live-ink": "#FFFFFF",
      positive: "#34CF98",
      "positive-soft": "#0E2A20",
      caution: "#F2B54A",
      "caution-soft": "#2E2410",
      bar: "#3A4741",
      mast: "#111513",
      "mast-ink": "#E6EBE8",
      "mast-muted": "#9AA49F",
    },
  },
  {
    key: "c",
    label: "C",
    name: "インク×サイソク・オレンジ",
    short: "オレンジ",
    concept: "温かい紙色と墨の黒、太い罫線。オレンジは数字の強調と選択中だけに使う雑誌の組み方。",
    accentUse: "オレンジ＝最安の棒と数字・選択中の下線（速報は朱色）",
    shape: {
      "radius-sm": "2px",
      "radius-md": "2px",
      "radius-lg": "4px",
      shadow: "none",
      "shadow-lift": "0 0 0 2px var(--ink)",
      rule: "3px",
      "font-num": SANS,
    },
    light: {
      bg: "#F6F2EA",
      surface: "#FFFDF8",
      "surface-2": "#EDE7DC",
      ink: "#17140F",
      "ink-soft": "#3A342C",
      muted: "#554E44",
      line: "#E2DACD",
      "line-strong": "#C9BFAE",
      accent: "#BF3F0A",
      "accent-fill": "#E2530A",
      "accent-ink": "#17140F",
      "accent-soft": "#FCE5D2",
      live: "#B8300C",
      "live-ink": "#FFFFFF",
      positive: "#2F6B2A",
      "positive-soft": "#E7F0DF",
      caution: "#8F5600",
      "caution-soft": "#FBF0DC",
      bar: "#17140F",
      mast: "#F6F2EA",
      "mast-ink": "#17140F",
      "mast-muted": "#554E44",
    },
    dark: {
      bg: "#13110E",
      surface: "#1C1915",
      "surface-2": "#25211C",
      ink: "#F2ECE2",
      "ink-soft": "#D2CABD",
      muted: "#AEA597",
      line: "#2F2A23",
      "line-strong": "#4A4238",
      accent: "#FF8B42",
      "accent-fill": "#FF7A2A",
      "accent-ink": "#17100A",
      "accent-soft": "#3A2414",
      live: "#C93A16",
      "live-ink": "#FFFFFF",
      positive: "#8FD17E",
      "positive-soft": "#1E2C18",
      caution: "#F2B54A",
      "caution-soft": "#2E2410",
      bar: "#A79E90",
      mast: "#13110E",
      "mast-ink": "#F2ECE2",
      "mast-muted": "#AEA597",
    },
  },
];

/** トークンを CSS 変数（--bg など）の style に直す */
export function tokenStyle(dir: Direction, mode: Mode): Record<string, string> {
  const style: Record<string, string> = {};
  for (const [k, v] of Object.entries({ ...dir.shape, ...dir[mode] })) style[`--${k}`] = v;
  return style;
}

/* ------------------------------------------------------------------ */
/* 料金の計算（/ai-pricing の PricingBoard と同じ前提）                   */
/* ------------------------------------------------------------------ */

export type ActivityKey = "chat" | "summary" | "blog" | "image";

export const ACTIVITIES: { key: ActivityKey; label: string; per: "day" | "month"; unit: string; input: number; output: number }[] = [
  { key: "chat", label: "チャットで質問", per: "day", unit: "回", input: 500, output: 300 },
  { key: "summary", label: "長い資料を要約", per: "day", unit: "本", input: 8000, output: 800 },
  { key: "blog", label: "ブログ記事を作成", per: "month", unit: "本", input: 1000, output: 4000 },
  { key: "image", label: "画像を読ませる", per: "day", unit: "枚", input: 1500, output: 300 },
];

export type Usage = Record<ActivityKey, number>;

export const PRESETS: { key: string; label: string; usage: Usage }[] = [
  { key: "light", label: "少し", usage: { chat: 3, summary: 0, blog: 1, image: 0 } },
  { key: "normal", label: "ふつう", usage: { chat: 10, summary: 1, blog: 4, image: 1 } },
  { key: "heavy", label: "たくさん", usage: { chat: 50, summary: 5, blog: 20, image: 10 } },
];

export const RATE = 150;

export function monthlyTokens(usage: Usage) {
  let input = 0;
  let output = 0;
  let actions = 0;
  for (const a of ACTIVITIES) {
    const times = usage[a.key] * (a.per === "day" ? 30 : 1);
    input += times * a.input;
    output += times * a.output;
    actions += times;
  }
  return { input, output, actions };
}

/** 月の費用（円） */
export function monthlyYen(model: { input: number; output: number }, usage: Usage): number {
  const t = monthlyTokens(usage);
  return ((model.input * t.input + model.output * t.output) / 1_000_000) * RATE;
}

/** 1円未満も読める円の数字部分（「17」「0.05」「1,700」） */
export function yenDigits(value: number): string {
  if (value <= 0) return "0";
  if (value < 1) return value.toFixed(2);
  if (value < 10) return value.toFixed(1);
  if (value < 100) return String(Math.round(value));
  return (Math.round(value / 10) * 10).toLocaleString("ja-JP");
}

export function usd(value: number | null): string {
  if (value === null) return "—";
  const min = value >= 1 && value % 1 === 0 ? 0 : 2;
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: min, maximumFractionDigits: 2 })}`;
}
