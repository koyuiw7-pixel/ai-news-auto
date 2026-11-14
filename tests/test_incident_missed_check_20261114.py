"""毎朝の見逃しチェックの話題を、一覧で終わらせず事故の見張りに入れる（2026-11-14 オーナー「全然最速でもない」・台帳 W44）。

見逃しチェックの Issue は「他社だけの話題」を並べるだけで、何もそれを記事にしなかった。「自分は対象か」の事故（情報流出・回収・障害）の
見出しは、会社自身のお知らせを探して速報レーンへ（無ければ話題のレーン＝報道2社以上の決まりへ）回し、Issue には回した結果を書く。
"""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import incident_watch as iw  # noqa: E402
import radar  # noqa: E402

NOW = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
CFG = iw.CONFIG
PDF = "https://global-assets.irdirect.jp/pdf/menu_file/4482/20261102152018_7983.pdf"
NOTICE = ("「ネットマイル」における不正アクセスによる個人情報漏洩の可能性に関するお知らせ\n2026年11月2日\n株式会社ネットマイル\n"
          "当社が運営する「ネットマイル」において、第三者による不正アクセスがあり、会員情報が漏えいした可能性があります。" + "詳しい説明です。" * 170)
MUJI = {"slug": "muji-card-number-leak-2021", "title": "無印良品のMUJI Card、2021年7月までの入会者109万件のカード番号が流出の可能性",
        "seoTitle": "", "urls": ["https://www.ryohin-keikaku.jp/news/articles/2026_1104_02"], "publishedAt": NOW - timedelta(hours=3),
        "madeAt": NOW - timedelta(hours=3), "sourcePublishedAt": None, "detectedAt": None, "incident": None}


def page(text="", links=None):
    return {"text": text, "links": links or [], "title": "", "published": ""}


class MissedCheckTest(unittest.TestCase):
    """毎朝の見逃しチェックの話題を、一覧で終わらせず同じ流れに入れる"""

    def test_rows_and_section(self):
        gaps = [{"title": "ネットマイルに不正アクセス、最大約549万人の情報流出か", "url": "https://news.yahoo.co.jp/pickup/1", "outlets": {"Yahoo!ニュース", "時事通信"},
                 "published": NOW, "also": [{"title": "ネットマイル、549万人の情報漏えいの可能性", "outlet": "時事通信", "url": "https://www.jiji.com/jc/article?k=1"}]}]
        rows = radar.incident_rows(gaps, [])
        self.assertEqual([r["source"] for r in rows], ["Yahoo!ニュース", "時事通信"])
        text = radar.incident_section(gaps, [], NOW, enqueue=lambda rows, now: ["- ネットマイル（情報流出）: **速報レーンに回しました** → https://x"])
        self.assertIn("事故の見張りに回した話題", text)
        self.assertIn("速報レーンに回しました", text)
        self.assertEqual(radar.incident_section(gaps, [], NOW, enqueue=lambda rows, now: []), "")

        def boom(rows, now):
            raise RuntimeError("x")

        self.assertIn("回せませんでした", radar.incident_section(gaps, [], NOW, enqueue=boom))

    def test_enqueue_external_reports_what_was_and_was_not_enqueued(self):
        rows = [
            {"title": "ネットマイルに不正アクセス、最大約549万人の情報流出か", "url": "https://news.yahoo.co.jp/pickup/1", "source": "Yahoo!ニュース", "published": NOW},
            {"title": "無印良品、MUJI Cardのカード番号109万件が流出の可能性", "url": "https://news.yahoo.co.jp/pickup/2", "source": "Yahoo!ニュース", "published": NOW},
            {"title": "日経平均、3日続伸", "url": "https://news.yahoo.co.jp/pickup/3", "source": "Yahoo!ニュース", "published": NOW},
        ]
        pages = {"https://news.yahoo.co.jp/pickup/1": page("記事", [{"url": PDF, "text": "発表"}]), PDF: page(NOTICE)}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "incident_watch.json"
            lines = iw.enqueue_external(rows, NOW, lambda u: pages[u], CFG, path, [MUJI])
            state = iw.load_state(path)
        self.assertEqual(len(lines), 2)
        self.assertTrue(any("ネットマイル" in line and "速報レーンに回しました" in line for line in lines))
        self.assertTrue(any("良品計画" in line and "muji-card-number-leak-2021" in line for line in lines))
        self.assertEqual(state["items"]["breach:ネットマイル"]["status"], "queued")

    def test_workflow(self):
        missed = (ROOT / ".github" / "workflows" / "missed_check.yml").read_text("utf-8")
        self.assertIn("state/incident_watch.json", missed)
        self.assertIn("gh workflow run incident_watch.yml", missed)
        self.assertIn("actions: write", missed)
        src = (ROOT / "scripts" / "radar.py").read_text("utf-8")
        self.assertIn("report += incident_section(gaps, stories, now)", src)


if __name__ == "__main__":
    unittest.main()
