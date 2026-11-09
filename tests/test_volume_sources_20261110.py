"""2026-11-10 台帳 A69: 11/9 は記事が約90本で、100本に届かなかった。
原因は ①公式の新しい発表が1日 約130件（夜はほぼ0）しかない ②夜の穴埋め（使い方ガイド）が、公式ページが1枚しかない
お金・手続きの題材で「公式ページが足りない」と見送られ、AI の道具のガイドばかりになっていた。
①暮らしとお金の公式の発信元を足す ②手続きのガイドに公式の出典を足す（外部への通信なし）。"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import feeds  # noqa: E402
import genres  # noqa: E402

NEW = {"tdb", "nite", "kyoukaikenpo", "bousai", "fdma"}
# 11/9 に「公式ページが足りないので見送り」になっていた手続きのガイド（児童手当は 11/9 に読まれた記事の3位の話題）
STARVED = {
    "earthquake-insurance-deduction", "ideco-nencho", "fuyo-kojo", "kiso-kojo", "widow-single-parent", "shogaisha-kojo",
    "menkyo-koshin", "nenkin-teikibin", "kokunen-hokenryo", "jidou-teate", "ikukyu-kyufu", "kosodate-ecohome",
    "green-jutaku", "hikyojusha",
}
OFFICIAL = re.compile(r"\.go\.jp/|\.lg\.jp/|nenkin\.go\.jp|mlit\.go\.jp")


class VolumeSourcesTest(unittest.TestCase):
    def test_new_feeds_are_registered_and_valid(self):
        by_slug = {f["slug"]: f for f in feeds.BROAD_FEEDS}
        self.assertTrue(NEW <= set(by_slug), sorted(NEW - set(by_slug)))
        sections = {g.slug for g in genres.WEB_GENRES} | {"auto"}
        for slug in NEW:
            f = by_slug[slug]
            self.assertEqual(f["lang"], "ja", slug)
            self.assertEqual(f.get("type"), "html", slug)
            self.assertIn(f["section"], sections, slug)
            self.assertIn(f["kind"], ("gov", "company"), slug)
            self.assertTrue(f["url"].startswith("https://"), slug)
            for key in ("link_re", "include_re", "exclude_re"):
                if f.get(key):
                    re.compile(f[key])
        slugs = [f["slug"] for f in feeds.FEEDS + feeds.BROAD_FEEDS]
        self.assertEqual(len(slugs), len(set(slugs)), "slug が重なっている")

    def test_tdb_keeps_price_reports_and_drops_videos(self):
        page = """<ul>
          <li><a href="/report/economic/20261030-neage26y11/">物価・価格 「食品主要195社」価格改定動向調査 ― 2026年11月 飲食料品値上げ、年間2万品目超え</a><time>2026.10.30</time></li>
          <li><a href="/report/industry/20261019-movie-x/">動画 1分でわかる！「飲食料品卸売」の倒産動向</a><time>2026.10.19</time></li>
          <li><a href="/report/bankruptcy/flash/5271/">倒産速報 ある会社 東京都港区 特別清算開始命令受ける</a><time>2026.11.06</time></li>
        </ul>"""
        feed = feeds.FEEDS_BY_SLUG["tdb"]
        items = feeds.parse_html_list(feed, page.encode())
        kept = [i["title"] for i in items if not re.search(feed["exclude_re"], i["title"])]
        self.assertEqual(len(kept), 1)
        self.assertIn("値上げ", kept[0])

    def test_fdma_only_home_safety(self):
        feed = feeds.FEEDS_BY_SLUG["fdma"]

        def keep(title: str) -> bool:
            return bool(re.search(feed["include_re"], title)) and not re.search(feed["exclude_re"], title)

        self.assertTrue(keep("リチウムイオン電池火災に関する予防啓発映像及びポスターの制作・発表"))
        self.assertTrue(keep("令和８年秋季全国火災予防運動の実施"))
        self.assertFalse(keep("弾道ミサイルを想定した住民避難訓練の実施"))
        self.assertFalse(keep("危険物の規制に関する規則の一部を改正する省令（案）等に対する意見公募"))

    def test_starved_procedure_guides_have_more_than_one_official_source(self):
        plan = json.loads((ROOT / "content" / "evergreen_plan.json").read_text("utf-8"))
        topics = {t["slug"]: t for t in plan["topics"]}
        for slug in STARVED:
            sources = topics[slug]["sources"]
            self.assertGreaterEqual(len(sources), 2, slug)
            self.assertEqual(len(sources), len(set(sources)), slug)
            for url in sources:
                self.assertTrue(url.startswith("https://"), url)
                self.assertRegex(url, OFFICIAL, url)

    def test_ledger_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A69 |")), "")
        self.assertIn("2026-11-10", row)
        self.assertIn("100本", row)


if __name__ == "__main__":
    unittest.main()
