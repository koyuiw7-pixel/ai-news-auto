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

    def test_clean_url_strips_tracking(self):
        self.assertEqual(d.clean_url("https://a.jp/x/?icid=CRP_1"), "https://a.jp/x/")
        self.assertEqual(d.clean_url("https://a.jp/faq/detail?faqId=27&icid=CRP"), "https://a.jp/faq/detail?faqId=27")

    def test_general_pages_follow_the_topic(self):
        self.assertTrue(d.general_urls({"title": "ドコモで顧客情報が流出"}))
        self.assertTrue(any("kantei" in u for u in d.general_urls({"title": "【地震】静岡県西部で最大震度5強"})))
        self.assertEqual(d.general_urls({"title": "ふるさと納税の期限"}), [])


if __name__ == "__main__":
    unittest.main()
