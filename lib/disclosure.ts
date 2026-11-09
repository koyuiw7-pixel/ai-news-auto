import { siteConfig } from "@/site.config";

/**
 * 広告・提携の開示の文面（フッター・/privacy・/disclaimer で同じものを使う）。
 *
 * Amazon アソシエイト（もしもアフィリエイト経由を含む）の承認が下りるまでは false のままにする。
 * 承認前に「Amazonのアソシエイトとして…収入を得ています」と書くと事実と違い、Amazon の運営規約
 * （関係を偽って述べることの禁止）にも反するため（2026-11-09。承認の連絡が来たら true にしてデプロイ）。
 * true にすると、運営規約 第5条の決まった文がフッター・/privacy・/disclaimer に出る。
 */
// 2026-11-09 夜: オーナーは 2026-10-29 に Amazon アソシエイトへ直接申し込み済み（トラッキングID saisokuai-22）で、
// その ID 付きのリンクが記事に出ている。参加中（審査前の仮の参加を含む）は第5条の表示が必要なので true にする。
// アカウントが閉じられた・ID 付きのリンクを外した場合は false に戻す。
export const AMAZON_ASSOCIATE_APPROVED = true;

/** Amazon アソシエイト・プログラム運営規約 第5条の表示（文言を変えない） */
export const AMAZON_ASSOCIATE_STATEMENT = `Amazonのアソシエイトとして、${siteConfig.siteName}は適格販売により収入を得ています。`;

/** 承認済みのときだけ Amazon の決まった文を返す（未承認なら null） */
export function amazonAssociateStatement(): string | null {
  return AMAZON_ASSOCIATE_APPROVED ? AMAZON_ASSOCIATE_STATEMENT : null;
}

/** 参加している提携の仕組み（ASP）。本当に参加しているものだけを書く */
export const AFFILIATE_PROGRAMS = ["A8.net（株式会社ファンコミュニケーションズ）"];
