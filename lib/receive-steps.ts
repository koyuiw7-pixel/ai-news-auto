/**
 * 計算機の結果のすぐ下に出す「受け取るまでの流れ」（①誰が ②どこへ ③いつまでに ④いつ入る）の型。
 * 中身は制度ごとの lib（child-allowance.ts・ikukyu-kyufu.ts・pension-support-benefit.ts）に、公式ページの記載どおりに書く。
 */
export const RECEIVE_STEP_LABELS = ["誰が", "どこへ", "いつまでに", "いつ入る"] as const;
export type ReceiveStepLabel = (typeof RECEIVE_STEP_LABELS)[number];
export type ReceiveGuide = {
  title: string;
  steps: { label: ReceiveStepLabel; text: string }[];
  /** 画面に出す公式の案内（1つ目を「くわしくは」のリンクにする） */
  sources: { href: string; label: string }[];
  /** 公式ページを開いて確かめた日（YYYY-MM-DD） */
  checked: string;
};
