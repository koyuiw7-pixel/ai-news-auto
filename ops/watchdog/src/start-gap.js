// 日本時間 6:00〜24:00 は昼の間隔（DAY_START_GAP_MIN）。それ以外は START_GAP_MIN
export function isDaytimeJst(now) {
  return (now.getUTCHours() + 9) % 24 >= 6;
}

export function startGapMin(env, now) {
  const day = Number(env.DAY_START_GAP_MIN);
  return isDaytimeJst(now) && day > 0 ? day : Number(env.START_GAP_MIN);
}
