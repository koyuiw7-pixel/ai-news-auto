"""2026-11-13 オーナー「とにかく数字。それさえ出るなら結構なんでもいい」: お知らせ・価値の薄い題名の門を、検索で読まれた型に合わせて狭める
（台帳 A26。点検 audit_20261113: 褒章の受章者 24人・役所の調査の公表 14人・限定商品やキャンペーンを止めていた）。
通すのは、固有名詞＋（年/日付か金額・数）のある 受章者の一覧／官公庁の調査・統計の公表／キャンペーン・割引・プレゼント／締め切りつきの募集 だけ。
審議会・検討会・委員会の開催、啓発月間、ライトアップなどは今までどおり止める。外部への通信なし。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import notice_gate as ng  # noqa: E402
import web_articles as w  # noqa: E402


def cand(title, source_name="x", section="lifestyle"):
    return {"title": title, "section": section, "source_slug": "x", "source_name": source_name}


class WinningNoticeTest(unittest.TestCase):
    def test_honours_and_government_surveys_pass(self):
        for title, kw in (
            ("令和8年秋の褒章は761人　藍綬443人・黄綬264人、名簿は都道府県別に公開", {}),
            ("国土交通省、令和8年秋の褒章受章者を発表", {}),
            ("総務省、9月の人口移動報告を公表　市区町村間の移動者数は5.6％減", {}),
            ("内閣府、9月の景気動向指数を公表　一致指数は0.5ポイント上昇", {}),
            ("令和7年賃金構造基本統計調査の結果を公表します", {"sourceName": "厚生労働省"}),  # 候補の題名に役所の名前が無いときは発信元で見る
        ):
            self.assertIsNone(ng.notice_reason({"title": title, **kw}), title)

    def test_empty_notices_still_blocked(self):
        for title, kind in (
            ("景気動向指数（令和8年9月分速報）", "statistics"),      # 題名が統計の名前（期間）だけ
            ("マネタリーベース（10月）", "statistics"),
            ("地ビール1-8月出荷量は2年連続増　首位はエチゴビール、55.1％は前年割れ", "statistics"),  # 官公庁の統計ではない
            ("トヨタ、2026年度上半期の販売・生産・輸出実績を発表", "statistics"),
            ("財務省、製造たばこの小売定価の認可情報を随時公開　11月分", "listing"),
            ("東京都、11月はヤミ金融被害防止強化月間　無料相談や啓発イベント実施", "campaign"),
            ("厚労省、2026年の表彰者を決定　審議会の答申どおり", "listing"),
            ("サイバーエージェント、2026年9月期の通期決算を11月11日15時半に発表へ", "earnings-date"),
            ("財務省が研究会の議事要旨を公開　第2回会合まで", "minutes"),
        ):
            self.assertEqual(ng.notice_reason({"title": title}), kind, title)
        # 年・日付も数も無い受章者の知らせは通さない
        self.assertEqual(ng.notice_reason({"title": "褒章の受章者について"}), "listing")

    def test_low_value_gate_passes_only_winning_shapes(self):
        ok = (
            "マクドナルド、11月20日から「三角チョコパイ」半額キャンペーン",
            "ユニクロ感謝祭、11月21日から セールで最大3,000円引き",
            "PayPay、12月1日から最大20%のポイント還元",
            "東京都、省エネ家電の補助 申請を募集　12月25日まで",
        )
        for title in ok:
            self.assertIsNone(w.broad_prefilter(cand(title)), title)
        blocked = (
            "キャンペーン実施のお知らせ",                              # 固有名詞も日付も無い
            "JFA マルチスポーツチャレンジ 追加募集",                    # 締め切りが無い募集
            "人とペットの災害対策ガイドライン検討会の開催について",
            "AI利活用・マッチングセミナーを札幌市で開催",
            "都庁舎を11月14日にライトアップ キャンペーン",
            "中央環境審議会 第12回部会を11月20日に開催 プレゼント",
            "当社が「DXアワード2026」を受賞しました",                   # 自社の受賞の告知は受章者の一覧ではない
            "ローソン、新卒採用の募集を開始 キャンペーン 11月20日まで",  # ほかの語（採用・新卒）が残る
        )
        for title in blocked:
            self.assertRegex(str(w.broad_prefilter(cand(title))), "価値の薄いお知らせ", title)

    def test_helpers(self):
        self.assertTrue(ng.has_proper_noun("マクドナルドの半額キャンペーン"))
        self.assertFalse(ng.has_proper_noun("キャンペーン実施のお知らせ"))   # よくある語は固有名詞に数えない
        self.assertTrue(ng.has_fact("12月1日から") and ng.has_fact("最大3,000円") and ng.has_fact("2026年"))
        self.assertFalse(ng.has_fact("キャンペーンを実施"))
        self.assertTrue(ng.low_value_exempt("東京都、補助の申請を募集 12月25日まで", "募集"))
        self.assertFalse(ng.low_value_exempt("東京都、補助の申請を募集", "募集"))
        self.assertFalse(ng.low_value_exempt("マクドナルド、11月20日に説明会 キャンペーン", "キャンペーン"))

    def test_axis_and_publish_gate_let_the_winners_through(self):
        rec = {"title": "令和8年秋の褒章は761人　藍綬443人・黄綬264人、名簿は都道府県別に公開", "body": "x" * 2000,
               "genreSlug": "public", "tags": ["国土交通省"], "channelSlug": "mlit-press", "sourceUrl": "https://www.mlit.go.jp/x"}
        self.assertIsNone(indexnow.publish_block_reason(rec))
        self.assertIsNone(indexnow.noindex_reason(rec))
        self.assertFalse(indexnow.candidate_off_focus("public", "令和8年秋の褒章受章者について", "", "mlit-press"))
        # 門そのものは残っている
        self.assertEqual(indexnow.publish_block_reason({**rec, "title": "財務省、製造たばこの小売定価の認可情報を随時公開"}), "notice")

    def test_site_badge_rule_is_unchanged(self):
        # サイトの札（lib/verdict.ts・台帳 A27）は今までどおり: 受章者の一覧・統計の記事に「申し込める／使える」の札を出さない
        self.assertNotIn("neverPass", ng.rules())
        self.assertNotIn("winnerExempt", (ROOT / "lib" / "verdict.ts").read_text("utf-8"))
        # 個人の受章の知らせ（取り下げ済みの型）は軸に入れない
        self.assertFalse(indexnow.life_link("国立天文台の本間希樹教授が紫綬褒章を受章"))

    def test_never_pass_words(self):
        # NEVER_PASS は題名のどこにあっても効く（ライトアップ・啓発・委員会）
        for word in ("ライトアップ", "啓発", "委員会", "検討会", "審議会", "月間"):
            self.assertTrue(ng.NEVER_PASS_RE.search(f"東京都、11月14日に{word}"), word)


if __name__ == "__main__":
    unittest.main()
