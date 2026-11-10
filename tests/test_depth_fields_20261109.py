"""2026-11-09 オーナー指摘（台帳 A66）: 「今やること」が一般論で浅い。公式ページにだけある「なるほど」・公式窓口の URL と辿り方・
なぜ起きた・不安への答えを足す。唯一の門は「嘘をつかない」ので、ページに無い数字・名前・URL はプログラムが外す。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import depth_fields as d  # noqa: E402

NOTICE = "https://www.docomo.ne.jp/info/notice/page/261106_00_m.html"
CONFIRM = "https://www.docomo.ne.jp/info/anti-phishing/confirmation/"
NPA = "https://www.npa.go.jp/bureau/safetylife/sos47/case/"
PAGES = [
    {"url": NOTICE, "final_url": NOTICE, "name": "お知らせ", "text": "ドコモからのお知らせ\n（３）原因\n外部からの不正アクセス\n・特設ダイヤル\n電話番号 ：0120-451-360\n（受付時間：午前9時～午後8時）\n３．お問い合わせ",
     "links": [{"url": CONFIRM, "text": "本物のドコモからの連絡か確認する"}]},
    {"url": CONFIRM, "final_url": CONFIRM, "name": "確認", "text": "送信元表示名\nNTT DOCOMO\nDoCoMo SMS\nメッセージRやメッセージSは、なりすましはありません。",
     "links": [{"url": "https://www.docomo.ne.jp/info/anti-phishing/inquiry/", "text": "お問い合わせ・ご相談窓口"}]},
    {"url": NPA, "final_url": NPA, "name": "警察庁", "text": "特殊詐欺対策では、何よりも「犯人と話をしない」ことが大切です。", "links": [], "general": True},
]


class ValidateTest(unittest.TestCase):
    def test_keeps_sourced_items_and_drops_invented_numbers(self):
        data = {
            "insight": [
                {"text": "本物のSMSの送信元は「NTT DOCOMO」「DoCoMo SMS」などの決まった名前です。", "source": CONFIRM},
                {"text": "特設ダイヤルは 0120-999-999 で24時間受け付けています。", "source": NOTICE},  # ページに無い番号
                {"text": "怪しいメールのURLは開かないようにしましょう。", "source": NOTICE},  # 一般論
                {"text": "メッセージRはなりすましがない、とドコモは説明しています。", "source": "https://example.com/"},  # 読んでいないページ
            ],
            "official_desk": [
                {"name": "特設ダイヤル", "url": NOTICE + "?icid=abc", "how_to": ["ドコモからのお知らせ", "３．お問い合わせ"], "phone": "0120-451-360",
                 "hours": "午前9時～午後8時", "note": "", "source": NOTICE},
                {"name": "相談窓口", "url": "https://www.docomo.ne.jp/info/anti-phishing/inquiry/", "how_to": [], "phone": "", "hours": "",
                 "note": "", "source": CONFIRM},
                {"name": "作った窓口", "url": "https://www.docomo.ne.jp/made-up/", "how_to": [], "phone": "", "hours": "", "note": "", "source": NOTICE},
            ],
            "today_steps": [
                {"action": "SMSの送信元を公式の一覧と見比べる", "steps": ["送信元の表示名を見る"], "url": CONFIRM, "source": CONFIRM},
                {"action": "対象か分からなければ特設ダイヤル 0120-451-360 に電話する", "steps": [], "url": "", "source": NOTICE},
            ],
            "cause": {"text": "原因は「外部からの不正アクセス」とされ、侵入経路は調査中です。", "status": "investigating", "source": NOTICE},
            "worries": [
                {"q": "家族に詐欺の電話が来る？", "a": "警察庁は「犯人と話をしない」ことが大切だとしています。", "action": "知らない番号には出ない",
                 "source": NPA, "general": False, "action_source": ""},
                {"q": "どこに相談すればいい？", "a": "特設ダイヤル 0120-451-360（午前9時～午後8時）が案内されています。", "action": "知らない番号からの電話には出ない",
                 "source": NOTICE, "general": False, "action_source": NPA},
                {"q": "補償はある？", "a": "1人あたり5000円の補償があります。", "action": "", "source": NOTICE, "general": False, "action_source": ""},
            ],
        }
        out, dropped = d.validate(data, PAGES, {"body": "", "lede": ""})
        self.assertEqual([i["source"] for i in out["insight"]], [CONFIRM])
        self.assertEqual([x["name"] for x in out["officialDesk"]], ["特設ダイヤル", "相談窓口"])
        self.assertEqual(out["officialDesk"][0]["url"], NOTICE)  # 計測用の icid を外す
        self.assertEqual(out["officialDesk"][0]["phone"], "0120-451-360")
        self.assertEqual(out["officialDesk"][0]["howTo"], ["ドコモからのお知らせ", "３．お問い合わせ"])
        self.assertEqual(len(out["todaySteps"]), 2)
        self.assertEqual(out["cause"]["status"], "investigating")
        # 一般の注意のページが出典の答えには、必ず general の札が付く（LLM が false と書いても）
        self.assertTrue(out["worries"][0]["general"])
        self.assertTrue(out["worries"][1]["actionGeneral"])
        self.assertEqual(len(out["worries"]), 2)  # 作った金額の答えは外す
        self.assertTrue(any("5000" in x for x in dropped))

    def test_insight_and_cause_never_cite_general_pages(self):
        data = {"insight": [{"text": "警察庁は「犯人と話をしない」ことが大切だとしています。", "source": NPA}],
                "official_desk": [], "today_steps": [],
                "cause": {"text": "「犯人と話をしない」ことが大切です。", "status": "stated", "source": NPA}, "worries": []}
        out, _ = d.validate(data, PAGES, {})
        self.assertNotIn("insight", out)
        self.assertNotIn("cause", out)

    def test_apply_fields_keeps_short_actions_in_sync(self):
        rec = {"todayActions": ["古い1", "古い2"]}
        d.apply_fields(rec, {"todaySteps": [{"action": "新しい1", "source": NOTICE}, {"action": "新しい2", "source": NOTICE}]})
        self.assertEqual(rec["todayActions"], ["新しい1", "新しい2"])
        self.assertIn("depthAt", rec)

    def test_headings_are_per_article_short_and_true(self):
        data = {"insight": [{"text": "本物のSMSの送信元は「NTT DOCOMO」「DoCoMo SMS」などの決まった名前です。", "source": CONFIRM}],
                "official_desk": [], "today_steps": [], "worries": [], "decision_guide": [],
                "cause": {"text": "原因は「外部からの不正アクセス」とされています。", "status": "investigating", "source": NOTICE},
                "headings": {"insight": "本物のドコモのSMSは、送信元の名前で見分けられる｜", "cause": "なぜ起きた？",
                             "steps": "手順", "desk": "", "worries": "", "guide": ""}}
        out, dropped = d.validate(data, PAGES, {})
        self.assertEqual(out["depthHeadings"], {"insight": "本物のドコモのSMSは、送信元の名前で見分けられる"})  # 「｜」は外す・決まり文句は落とす・中身の無い欄は付けない
        self.assertTrue(any("決まり文句" in x for x in dropped))

    def test_decision_guide_marks_general_rows(self):
        data = {"insight": [], "official_desk": [], "today_steps": [], "worries": [], "cause": {"text": "", "status": "stated", "source": ""},
                "decision_guide": [
                    {"question": "電話番号を変える？", "situation": "まだ不審な電話は来ていない", "recommend": "番号はそのままでよい",
                     "reason": "警察庁は「犯人と話をしない」ことが大切だとしています。", "source": NPA, "general": False},
                    {"question": "電話番号を変える？", "situation": "何度も来る", "recommend": "検討する",
                     "reason": "店頭の手数料は9,999円かかります（作った数字）。", "source": NOTICE, "general": False}]}
        out, dropped = d.validate(data, PAGES, {})
        self.assertEqual(len(out["decisionGuide"]), 1)
        self.assertTrue(out["decisionGuide"][0]["general"])

    def test_clean_url_strips_tracking(self):
        self.assertEqual(d.clean_url("https://a.jp/x/?icid=CRP_1"), "https://a.jp/x/")
        self.assertEqual(d.clean_url("https://a.jp/faq/detail?faqId=27&icid=CRP"), "https://a.jp/faq/detail?faqId=27")

    def test_general_pages_follow_the_topic(self):
        self.assertTrue(d.general_urls({"title": "ドコモで顧客情報が流出"}))
        self.assertTrue(any("kantei" in u for u in d.general_urls({"title": "【地震】静岡県西部で最大震度5強"})))
        self.assertEqual(d.general_urls({"title": "ふるさと納税の期限"}), [])


class NotStatedTest(unittest.TestCase):
    """2026-11-10 SEO A4・LLMO-A4: 答えが「このページには書かれていません」の不安は書かない（2つ未満なら欄ごと書かない）"""

    def worries(self, rows):
        data = {"worries": [{"q": q, "a": a, "action": "", "source": NOTICE, "general": False, "action_source": ""} for q, a in rows]}
        return d.validate(data, PAGES, {"body": "", "lede": ""})

    def test_not_stated_answer_is_dropped(self):
        out, dropped = self.worries([
            ("補償はある？", "このページには、補償の有無は書かれていません。お問い合わせは特設ダイヤルで受け付けています。"),
            ("どこに相談すればいい？", "特設ダイヤル 0120-451-360 が案内されています。受付時間はこのページには書かれていません。"),
            ("原因は分かっている？", "原因は外部からの不正アクセスとされています。"),
        ])
        self.assertEqual([w["q"] for w in out["worries"]], ["どこに相談すればいい？", "原因は分かっている？"])
        self.assertEqual(out["worries"][0]["a"], "特設ダイヤル 0120-451-360 が案内されています。")  # 2文目の「書かれていません」は外す
        self.assertTrue(any("答えになっていない" in x for x in dropped))

    def test_block_is_not_written_when_fewer_than_two_remain(self):
        out, _ = self.worries([
            ("補償はある？", "このページには、補償の有無は書かれていません。"),
            ("原因は分かっている？", "原因は外部からの不正アクセスとされています。"),
        ])
        self.assertNotIn("worries", out)

    def test_prompt_says_drop_unanswerable_questions(self):
        self.assertIn("答えられない問いは作らない", d.PROMPT)

    def test_shared_autofix_trims_not_stated_on_every_path(self):
        # 2026-11-10: gpt_review の書き直しや clean_faq の2文目から「まだ発表されていません」が記事に残った。共通の autofix で外す
        import article_style
        import web_articles

        rec = {"faq": [{"q": "日本でも？", "a": "今回はEMEAの提携です。日本での予定は、まだ発表されていません。"},
                       {"q": "日本で使える？", "a": "使えます。"}],
               "worries": [{"q": "影響は？", "a": "統計の目的は基礎資料です。個別の会社への影響については書かれていません。"},
                           {"q": "補償は？", "a": "このページには、補償の有無は書かれていません。"}],
               "depthHeadings": {"worries": "こんな不安ありませんか"}}
        article_style.reader_order_autofix(rec)
        self.assertEqual(rec["faq"], [{"q": "日本でも？", "a": "今回はEMEAの提携です。"}, {"q": "日本で使える？", "a": "使えます。"}])
        self.assertNotIn("worries", rec)  # 不安が2つ未満になったら欄と見出しごと外す
        self.assertNotIn("depthHeadings", rec)
        rows = web_articles.clean_faq([{"q": "日本でも？", "a": "今回はEMEAの提携です。日本での予定は、まだ発表されていません。"}])
        self.assertEqual(rows, [{"q": "日本でも？", "a": "今回はEMEAの提携です。"}])

    def test_corpus_has_no_not_stated_answers(self):
        import nonanswer
        counts = nonanswer.corpus_counts(Path(__file__).resolve().parent.parent / "content")
        self.assertEqual(counts["articleAnswers"], 0, "python3 scripts/sweep_not_stated.py で外す")
        self.assertEqual(counts["guideAnswers"], 0, "python3 scripts/sweep_not_stated.py で外す")


if __name__ == "__main__":
    unittest.main()
