"""「すぐにできること」のそばの PR（ACTION_ADS）と、11/8 追加の A8 提携の設定を、通信なしで確かめる。"""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a8_import  # noqa: E402
import aff_stats  # noqa: E402

A8MAT = re.compile(r"^[0-9A-Z]+(?:\+[0-9A-Z]+){3}$")
# 公式の名前と中立な1行だけにする（根拠のない売り文句を入れない）
HYPE = re.compile(r"最安|最強|No\.?1|ナンバーワン|一番|業界初|必ず|絶対|今だけ|お得|激安|｜")


class ActionAdsTest(unittest.TestCase):
    def setUp(self):
        self.offers = json.loads((ROOT / "content/offers.json").read_text(encoding="utf-8"))
        self.links = json.loads((ROOT / "affiliate_links.json").read_text(encoding="utf-8"))
        self.keys = {meta["key"] for meta in a8_import.PARTNERS.values()}

    def test_offers_json_matches_importer(self):
        self.assertEqual(self.offers["actionAds"], a8_import.ACTION_ADS)

    def test_every_action_partner_has_a_live_affiliate_link(self):
        for rule in a8_import.ACTION_ADS:
            for key in rule["partners"]:
                with self.subTest(rule=rule["key"], key=key):
                    self.assertIn(key, self.keys)
                    partner = self.offers["partners"][key]
                    self.assertFalse(partner.get("hidden"))
                    self.assertIn(partner["program"], self.links)
                    self.assertTrue(partner["link"].startswith("https://px.a8.net/svt/ejp?a8mat="))
                    self.assertRegex(partner["link"].split("a8mat=")[1], A8MAT)

    def test_copy_is_neutral(self):
        for rule in a8_import.ACTION_ADS:
            self.assertNotRegex(rule["title"], HYPE)
            for key in rule["partners"]:
                partner = self.offers["partners"][key]
                with self.subTest(key=key):
                    self.assertNotRegex(partner["name"], HYPE)
                    self.assertNotRegex(partner["note"], HYPE)
                    self.assertLessEqual(len(partner["note"]), 70)

    def test_rules_are_valid_regex_and_ordered(self):
        order = [rule["key"] for rule in a8_import.ACTION_ADS]
        # 情報流出（ドコモなど通信会社の名前が出る）を、スマホ回線の見直しより先に当てる
        self.assertLess(order.index("leak"), order.index("mobile"))
        # ふるさと納税の記事は「確定申告」の語も出るので、ふるさと納税を先に当てる
        self.assertLess(order.index("furusato"), order.index("tax"))
        for rule in a8_import.ACTION_ADS:
            re.compile(rule["match"])
            self.assertGreaterEqual(rule.get("max", 2), 1)

    def test_new_programs_from_20261108_are_registered(self):
        ids = {
            "s00000025743001", "s00000020080001", "s00000025626001", "s00000027418001", "s00000023371001",
            "s00000022499001", "s00000000979014", "s00000017718057", "s00000015110002", "s00000004657003",
            "s00000023934001", "s00000021712001", "s00000021185002", "s00000014765001", "s00000019543001",
            # 11/8 夜の追加
            "s00000013511010", "s00000007476001", "s00000010789007", "s00000000040018", "s00000000489041",
            "s00000005230001", "s00000000218001", "s00000010685001",
        }
        self.assertLessEqual(ids, set(a8_import.PARTNERS))
        for pid in ids:
            meta = a8_import.PARTNERS[pid]
            if "a8" in meta:
                with self.subTest(pid=pid):
                    self.assertRegex(meta["a8"][0], A8MAT)
                    self.assertTrue(meta["a8"][1].isdigit())
                    self.assertEqual(self.offers["partners"][meta["key"]]["programId"], pid)

    def test_import_uses_inline_material_without_tsv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            links, offers = root / "links.json", root / "offers.json"
            links.write_text("{}", encoding="utf-8")
            offers.write_text(json.dumps({"topics": [], "partners": {}}), encoding="utf-8")
            with patch.multiple(a8_import, TSV=root / "missing.tsv", LINKS=links, OFFERS=offers), redirect_stdout(io.StringIO()):
                self.assertEqual(a8_import.main(), 0)
            got = json.loads(offers.read_text(encoding="utf-8"))
            got_links = json.loads(links.read_text(encoding="utf-8"))
        self.assertEqual(got["partners"]["elpio"]["link"], "https://px.a8.net/svt/ejp?a8mat=4BGGBL+C9RNN6+4AXS+5Z6WY")
        self.assertEqual(got_links["エルピオでんき"]["pixel"], "https://www19.a8.net/0.gif?a8mat=4BGGBL+C9RNN6+4AXS+5Z6WY")
        # 弥生は既存の program 名（affiliate_links.json のキー）のまま、表示名だけ変える
        self.assertEqual(got["partners"]["yayoi-kakutei"]["program"], "弥生シリーズ")
        self.assertIsNone(got["partners"]["epos"]["image"])
        self.assertEqual(got["actionAds"], a8_import.ACTION_ADS)


class PositionStatsTest(unittest.TestCase):
    def test_action_ad_clicks_are_reported_separately(self):
        rows = [{"pos": "action-ad-1", "clicks": 2}, {"pos": "action-ad-2", "clicks": 1}, {"pos": "ranking-inline-1", "clicks": 4}]
        summary = dict(aff_stats.positions_summary(rows))
        self.assertEqual(summary["すぐにできることの下（本文中のPR）"], 3)
        self.assertEqual(summary["本文中の商品枠"], 4)
        self.assertEqual(aff_stats.position_group("action-ad"), "action-ad")
        self.assertEqual(aff_stats.position_group("other"), "other")


class ComponentWiringTest(unittest.TestCase):
    def test_action_ad_block_is_labelled_and_tracked(self):
        src = (ROOT / "components/ActionAd.tsx").read_text(encoding="utf-8")
        self.assertIn('data-aff-pos="action-ad"', src)
        self.assertIn("AFFILIATE_REL", src)
        self.assertIn("PR", src)
        self.assertIn("広告", src)
        rel = (ROOT / "lib/affiliate.ts").read_text(encoding="utf-8")
        self.assertIn('AFFILIATE_REL = "sponsored nofollow', rel)
        # クリックの受け口が置き場所の名前を受け付ける形のまま
        aff = (ROOT / "cloudflare/aff.ts").read_text(encoding="utf-8")
        pos = re.search(r"const POS = /(.+)/;", aff).group(1)
        self.assertRegex("action-ad-2", pos)

    def test_both_article_layouts_render_it_after_today_actions(self):
        for path in ("app/articles/[slug]/page.tsx", "components/noir/noirArticlePage.tsx"):
            src = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                today = src.index("<TodayActions actions={todayActions} />}")
                self.assertLess(today, src.index("<ActionAd ad={actionAd}"))
                self.assertLess(src.index("<ActionAd ad={actionAd}") - today, 300)


if __name__ == "__main__":
    unittest.main()
