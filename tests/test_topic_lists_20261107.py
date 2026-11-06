"""2026-11-07 オーナー「旬の情報をまとめてあげたり」（台帳 A52）: 値上げ・障害・リコール・サービス終了の一覧を、公開中の記事から規則で作る。
外部への通信・LLM なし。"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import topic_lists as tl  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=JST)


def art(slug, title, lede="", **extra):
    base = {"slug": slug, "title": title, "lede": lede, "highlights": [], "genreSlug": "lifestyle", "body": "x" * 1600 + " 日本で使える",
            "sourceUrl": f"https://example.co.jp/{slug}", "sourceName": "公式", "publishedAt": "2026-11-06T10:00:00+09:00",
            "verdict": {"japan": "yes"}, "tags": ["家計"]}
    base.update(extra)
    return base


class ClassifyTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(tl.kinds_of(art("a", "サントリーが「響」「山崎」など値上げへ　2027年4月1日出荷分から")), ["price-hikes"])
        self.assertEqual(tl.kinds_of(art("b", "楽天モバイルで通信障害　一部でつながりにくい状態に")), ["outages"])
        self.assertEqual(tl.kinds_of(art("c", "ロータス「エリーゼ」611台をリコール　燃料ポンプを全車交換へ")), ["recalls"])
        self.assertEqual(tl.kinds_of(art("d", "Apple、新しい「Siri AI」を日本語で提供開始")), ["service-changes"])
        self.assertEqual(tl.kinds_of(art("e", "旧アプリのサポート終了へ　12月1日から使えなくなる")), ["service-changes"])

    def test_not_listed(self):
        for title in ("トヨタの営業利益が値上げ効果で増益", "OpenAI、夜間の障害対応を自動で行うAIエージェントを公開",
                      "J-Net21が民法改正と手形廃止を解説", "高速道路で交通事故　3人けが", "OpenAI、新モデルを提供開始"):
            self.assertEqual(tl.kinds_of(art("x", title)), [], title)

    def test_effective_is_copied_from_the_article(self):
        a = art("a", "サントリーが「響」「山崎」など値上げへ　2027年4月1日出荷分から")
        self.assertEqual(tl.effective(a), "2027年4月1日出荷分から")
        self.assertIsNone(tl.effective(art("b", "値上げへ", "理由は原材料の上昇です。")))


class BuildTest(unittest.TestCase):
    def test_build_lists_only_published_indexable_articles_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            rows = [
                art("old-hike", "郵便料金を値上げ　10月1日から", "はがきが85円になります。", publishedAt="2026-10-01T09:00:00+09:00"),
                art("new-hike", "電気料金を値下げ　12月分から", "月額が下がります。", publishedAt="2026-11-06T09:00:00+09:00"),
                art("dup", "電気料金を値下げ　12月分から（重複）", publishedAt="2026-11-06T09:30:00+09:00", duplicateOf="new-hike"),
                art("nosrc", "ガス料金を値上げ", sourceUrl=""),
            ]
            for r in rows:
                (d / f"{r['slug']}.json").write_text(json.dumps(r, ensure_ascii=False), "utf-8")
            out = tl.build(d, NOW)
        hikes = out["lists"]["price-hikes"]
        self.assertEqual([e["slug"] for e in hikes], ["new-hike", "old-hike"])
        self.assertEqual(hikes[0]["change"], "値下げ")
        self.assertEqual(hikes[0]["what"], "月額が下がります。")
        self.assertEqual(hikes[1]["month"], "2026-10")
        self.assertEqual(hikes[1]["effective"], "10月1日から")

    def test_site_wiring(self):
        lib = (ROOT / "lib" / "topic-lists.ts").read_text("utf-8")
        self.assertIn('import data from "@/content/topic_lists.json"', lib)
        for kind in ("price-hikes", "outages", "recalls", "service-changes"):
            self.assertIn(f'kind: "{kind}"', lib)
        for line in lib.splitlines():  # 題名の決まり（A50）: 「〜とは？」にしない
            if "title: (n)" in line:
                self.assertNotIn("とは", line)
        self.assertIn("ItemList", (ROOT / "components" / "TopicListView.tsx").read_text("utf-8"))
        self.assertIn("TopicListMembership", (ROOT / "app" / "articles" / "[slug]" / "page.tsx").read_text("utf-8"))
        self.assertIn("/roundups", (ROOT / "lib" / "sitemap.ts").read_text("utf-8"))
        self.assertIn("/roundups", (ROOT / "lib" / "nav.ts").read_text("utf-8"))
        self.assertIn("python scripts/topic_lists.py", (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8"))

    def test_ledger_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A52 |")), "")
        self.assertIn("2026-11-07", row)
        self.assertIn("一覧", row)


if __name__ == "__main__":
    unittest.main()
