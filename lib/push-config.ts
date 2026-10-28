/**
 * 速報のプッシュ通知の設定（画面 components/PushOptIn.tsx と送信側 cloudflare/push.ts の両方が読む）。
 *
 * VAPID の公開鍵は公開してよい値。対になる秘密鍵は Worker の secret（VAPID_PRIVATE_KEY）にだけある。
 * 鍵を作り直すと、いまの購読がすべて使えなくなる（読者は登録し直しになる）ので変えない。
 */
export const VAPID_PUBLIC_KEY = "BPzjJX1wahQ48HeDlmQ_FdIOImDxG-PSwHTv0QAZi1rarOz-tgfxDt8iUGltzYI0moT2SZ8AQoTHrC5RNeWAJPY";

/** 通知の決まりごと（画面の説明文もこの数字を使う） */
export const PUSH_RULES = {
  /** 1日（日本時間）に送る最大の回数 */
  perDay: 4,
  /** 前の通知からこの時間（分）は次を送らない（鳴りすぎ防止） */
  minGapMin: 60,
  /** 鳴らさない時間（日本時間）。この間の速報は朝に1本だけ送る */
  quietFrom: 22,
  quietUntil: 7,
  /** 生成からこの時間（分）より古い記事は送らない（遅れて届く「速報」を出さない） */
  maxAgeMin: 180,
};
