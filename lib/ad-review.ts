// 2026-11-12 オーナー承認（AdSense の2回目の不承認「有用性の低いコンテンツ」のあと）:
// 申し込み直し（11/26ごろ）までは、記事の PR の囲みを1記事に1つまで・本文の後ろだけにする。
// 「すぐにできること」の下の PR、本文の途中の PR、右の列・スマホの下の帯、収益導線のバナー、比較の一覧、Amazon/楽天の1行は出さない。
// 11/27 からは元の置き方に戻る（次の公開のときに切り替わる）。
export const AD_REVIEW_UNTIL = Date.parse("2026-11-27T00:00:00+09:00");

export function inAdReview(now: number = Date.now()): boolean {
  return now < AD_REVIEW_UNTIL;
}
