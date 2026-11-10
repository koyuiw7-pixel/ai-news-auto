"""出典の資料の日付・会議の回と記事の出来事の食い違いの門（scripts/source_date.py）と、取り下げの台帳が正しい書き直しを止めないこと（2026-11-10）。

きっかけ: kokuho-genkagaku-limit-proposal（commit 896838c2 で取り下げ）が、第205回（令和7年11月27日）の資料の案を、
第220回（令和8年11月11日）の部会の議題として書いた。fixtures/source_date_kokuho_20261110.json はその記事と出典4本の本文。
"""
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dedupe  # noqa: E402
import main as m  # noqa: E402
import source_date as sd  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "source_date_kokuho_20261110.json").read_text("utf-8"))
NOV10 = date(2026, 11, 10)
NOV11 = date(2026, 11, 11)
OLD_PDF = next(s for s in FIXTURE["sources"] if s["url"].endswith("001599957.pdf"))
NOTICE = next(s for s in FIXTURE["sources"] if s["url"].endswith("newpage_77211.html"))

# 11日の部会の資料が公表されたあとの、正しい資料（中身は試験用の例）
NEW_MATERIAL = {
    "url": "https://www.mhlw.go.jp/content/12401000/009999999.pdf",
    "name": "厚生労働省保険局（第220回社会保障審議会医療保険部会 資料2）",
    "title": "国民健康保険の保険料(税)の賦課(課税)限度額について",
    "text": "令和8年11月11日 第220回社会保障審議会医療保険部会 資料2\n国民健康保険の保険料(税)の賦課(課税)限度額について\n"
            "※ 令和8年度賦課限度額:医療分:93万円\n令和9年度は医療分を96万円とする(3万円の引上げ)。" + "説明。" * 100,
}


class StaleSource(unittest.TestCase):
    def test_identifies_the_old_pdf(self):
        ident = sd.identify(OLD_PDF, NOV10)
        self.assertEqual(ident["date"], date(2025, 11, 27))
        self.assertEqual(ident["meeting"], 205)
        self.assertEqual(sd.identify(NOTICE, NOV10)["meeting"], 220)

    def test_the_1110_article_is_stopped(self):
        problems = sd.check(sd.record_texts(FIXTURE["article"]), FIXTURE["sources"], NOV10)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("第205回", problems[0])
        self.assertIn("2025年11月27日", problems[0])
        self.assertIn("93万円", problems[0])
        self.assertIn("まだ資料が公表されていない会議", problems[1])

    def test_explicit_earlier_material_is_allowed(self):
        texts = [
            "国保料の上限、11日の部会で議題に　資料はまだ公表前",
            "11日の部会では、国民健康保険の保険料の賦課限度額が議題になる予定です。",
            "前年（第205回、令和7年11月27日）の資料では、令和8年度に医療分を92万円から93万円へ上げる案が示されていました。",
        ]
        self.assertEqual(sd.check(texts, FIXTURE["sources"], NOV10), [])

    def test_correct_rewrite_with_1111_materials_passes(self):
        texts = [
            "国保料の上限、医療分を3万円上げる案　11日の部会で示される",
            "11日の部会の資料では、令和9年度に医療分を93万円から96万円へ上げる案が示されました。",
            "前年の資料では、令和8年度に92万円から93万円へ上げる案でした。",
        ]
        self.assertEqual(sd.check(texts, [NEW_MATERIAL, NOTICE, OLD_PDF], NOV11), [])

    def test_different_meeting_number_is_stopped(self):
        nov5 = {"url": "https://www.mhlw.go.jp/content/x.pdf", "name": "第219回 医療保険部会 資料1",
                "text": "令和8年11月5日 第219回社会保障審議会医療保険部会 資料1\n後期高齢者の保険料を年8,000円上げる案。" + "説明。" * 100}
        texts = ["第220回の部会で、後期高齢者の保険料を年8,000円上げる案が示されています。"]
        problems = sd.check(texts, [nov5], NOV11)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("第219回", problems[0])

    def test_evergreen_guide_citing_old_law_passes(self):
        law = {"url": "https://www.mhlw.go.jp/stf/old.html", "name": "厚生労働省（改正法の概要）",
               "text": "令和6年4月1日 施行\n育児休業給付は賃金の67%。月額の上限は31万円。" + "説明。" * 100}
        texts = ["育児休業給付のしくみ", "2024年の改正法で決まったとおり、給付は賃金の67%で、月額の上限は31万円です。",
                 "手続きは勤め先を通じて、ハローワークに申請します。"]
        self.assertEqual(sd.check(texts, [law], NOV10), [])

    def test_unrelated_dates_in_old_year_do_not_misfire(self):
        texts = ["令和7年11月27日の部会で、医療分を93万円へ上げる案が示されました。"]
        self.assertEqual(sd.check(texts, [OLD_PDF], NOV10), [], "古い会議の日付をはっきり書いていれば通す")


class RetiredLedger(unittest.TestCase):
    def test_retired_kokuho_does_not_block_its_official_page(self):
        entry = json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]["kokuho-genkagaku-limit-proposal"]
        self.assertIs(entry["blockSource"], False)
        index = dedupe.load_recent(1)
        self.assertFalse(index.has_url("https://www.mhlw.go.jp/stf/newpage_77211.html"),
                         "11日の資料が出たあとの正しい書き直しは、同じ開催案内のページを出典にしてよい")

    def test_other_retired_sources_still_block(self):
        items = json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]
        blocked = [e["sourceUrl"] for e in items.values() if e.get("sourceUrl") and e.get("blockSource") is not False]
        self.assertTrue(blocked)
        self.assertTrue(dedupe.load_recent(1).has_url(blocked[0]))

    def test_new_article_never_reuses_the_retired_slug(self):
        slug = m.unique_slug("kokuho-genkagaku-limit-proposal", "abcd1234")
        self.assertNotEqual(slug, "kokuho-genkagaku-limit-proposal", "取り下げた slug はサイトが 410 を返す")
        self.assertTrue(slug.startswith("kokuho-genkagaku-limit-proposal-"))
        with mock.patch.object(m, "_retired_slugs", return_value=set()):
            self.assertEqual(m.unique_slug("kokuho-genkagaku-limit-proposal", "abcd1234"), "kokuho-genkagaku-limit-proposal")


if __name__ == "__main__":
    unittest.main()
