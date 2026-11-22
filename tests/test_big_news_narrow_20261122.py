"""2026-11-22 オーナー決定（台帳 A75）: 30本の外は読者の安全・お金の話だけ。海外の AI の自動の記事は日付で戻さない。"""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import news_mix  # noqa: E402
import pacing  # noqa: E402
import public_interest as pi  # noqa: E402
import ramp  # noqa: E402
import web_articles as w  # noqa: E402

NOW = datetime(2026, 11, 22, 12, tzinfo=pi.JST)


class DefinitionTest(unittest.TestCase):
    """題名は 11/8〜21 の実際の記事から"""

    def test_real_safety_and_money_stay_uncapped(self):
        for title, kind in (
            ("タイミー、求人事業者の最大22万6,662名分のメールアドレスが流出　対象と今やること", "breach"),
            ("SmartHRの役職員のNotion AIチャット記録の一部が流出のおそれ　対象は10月6日〜24日", "breach"),
            ("キリンのキャンペーン参加者1,825件が流出　LINE表示名とXユーザー名が対象", "breach"),
            ("モンテールのシュークリーム3品を回収　関東・新潟で販売、消費期限11月11日", "recall"),
            ("クボタのトラクター110台でブレーキ不具合のおそれ　MR700Hなど28車種が対象", "recall"),
            ("ドコモ・ファイナンスのWebログイン停止　11月17日15:45から、アプリは利用可", "outage"),
            ("証券会社の個人口座を狙う詐欺が増加　IOSCOが11月16日に警鐘", "scam"),
            ("JR京都線、11月20日に京都〜吹田間で運転見合わせ　岸辺駅で人身事故", "transport"),
            ("「フラボス」購入者への返金開始　対象と手続きはニコリオに確認", "refund"),
            ("電気料金を12月1日から値上げ", "price"),
            ("物価高対策の給付金、12月15日まで申請受付", "benefit"),
            ("家計簿アプリのサービス終了のお知らせ", "service-end"),
        ):
            self.assertEqual(pi.reader_urgent(title, NOW), kind, title)

    def test_corporate_news_counts_inside_30(self):
        for title in (
            "三菱UFJ、中間純利益が26.1%増の約1兆6,309億円　年間配当は100円を予想",
            "NVIDIAのフアンCEOが即日退任　後任はクレスCFOが暫定、決算は17日予定どおり",
            "「AQUOS sense11」auで11月26日発売　購入と応募で8,000円キャッシュバック",
            "「Gemini 4 Neon」順次提供　Proは月2,900円、複雑な作業に対応",
            "2026年のベストアプリは「あすけんダイエットアプリ」　Google Playの年間賞",
        ):
            self.assertIsNone(pi.reader_urgent(title, NOW), title)

    def test_policy_stats_and_lookalikes_are_not_urgent(self):
        for title in (
            "千葉豪雨を受け、都市型水害対策を3本柱で強化　国交省が方針",
            "個人情報漏えい、1,000人超など4類型で報告義務　速報は3〜5日以内",
            "ランサムウェアに備える3つの対策　AWSが防御・復旧・説明責任を解説",
            "生鮮食品を除く物価は2.2％上昇　電気代や野菜も前年を上回る",
            "ドンキの免税返金手数料が無料に　11月1日から新方式に対応",
            "中小企業に最大7,000万円の補助金　11月30日から申請受付",
            "介護保険料と給付・負担を議論　11月26日にYouTube配信",
        ):
            self.assertIsNone(pi.reader_urgent(title, NOW), title)

    def test_price_needs_a_near_date(self):
        self.assertIsNone(pi.reader_urgent("電気料金を値上げ", NOW))
        self.assertIsNone(pi.reader_urgent("電気料金を6月1日から値上げ", NOW))


class CapTest(unittest.TestCase):
    def count(self, entry, article):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "s.json").write_text(json.dumps(article), "utf-8")
            state = {"processed_web": {"s": {"slug": "s", "at": NOW.isoformat(), **entry}}}
            return pacing.live_today(state, NOW, Path(tmp))

    def test_corporate_breaking_is_counted(self):
        self.assertEqual(self.count({"major": True, "breaking": True}, {"title": "新型スマホを発表", "breaking": True, "fastLane": True}), 1)

    def test_safety_ordered_and_muse_are_not_counted(self):
        self.assertEqual(self.count({"major": True}, {"title": "会員情報が流出", "fastLane": True}), 0)
        self.assertEqual(self.count({"major": True, "ordered": True}, {"title": "新型スマホを発表", "fastLane": True}), 0)
        self.assertEqual(self.count({"writer": "muse"}, {"title": "新型スマホを発表", "museFile": "a.md"}), 0)

    def test_cap_free(self):
        self.assertTrue(w.cap_free({"title": "新型スマホを発表", "ordered": True}))
        self.assertTrue(w.cap_free({"title": "x", "_incident": {"kind": "breach"}}))
        self.assertTrue(w.cap_free({"title": "会員情報が流出"}))
        self.assertFalse(w.cap_free({"title": "新型スマホを発表", "fast": True}))

    def test_every_path_is_wired(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("if major and not cap_free(cand) and args.daily_cap and generated_today(state) >= args.daily_cap:", src)
        self.assertIn("if not cap_free(item) and iid not in state[\"processed_web\"] and pacing.routine_full(state, now):", src)
        self.assertIn('item["ordered"] = True', src)


class ForeignAiTest(unittest.TestCase):
    def test_no_date_resumes_it(self):
        self.assertTrue(ramp.FOREIGN_AI_STOPPED)
        for day in ("2026-11-26", "2026-11-27", "2026-12-31", "2027-06-01"):
            with mock.patch.object(news_mix, "datetime", wraps=datetime):
                self.assertTrue(news_mix.review_ai_blocks({"section": "ai", "lang": "en"}), day)

    def test_ramp_output_stays_zero_after_review(self):
        with tempfile.NamedTemporaryFile("r", suffix=".txt") as out, mock.patch.dict("os.environ", {"GITHUB_OUTPUT": out.name}), \
                mock.patch.object(ramp, "datetime") as clock:
            clock.now.return_value = datetime(2026, 11, 28, 12, tzinfo=ramp.JST)
            ramp.main()
            self.assertIn("foreign_ai_cap=0", out.read())

    def test_domestic_ai_is_not_blocked(self):
        self.assertFalse(news_mix.review_ai_blocks({"section": "ai", "lang": "ja"}))

    def test_breaking_post_condition_is_unchanged(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn('if major and breaking_record(item):\n            record["breaking"] = True', src)


if __name__ == "__main__":
    unittest.main()
