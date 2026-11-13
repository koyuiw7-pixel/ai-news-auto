"""2026-11-13 オーナー「とにかく数字」: 48時間で見送っていた発表を、通常のレーンでは96時間まで late の形で作る。
48時間が守っていたもの（ニュース用サイトマップ・速報に古い発表を出さない／いま起きている話題を終わってから書かない）は残す。"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import web_articles as w  # noqa: E402


def item(title, hours, slug="morinaga-news", **kw):
    return {"title": title, "source_slug": slug, "lang": "ja",
            "published_at": datetime.now(timezone.utc) - timedelta(hours=hours), **kw}


class StaleCutoffTest(unittest.TestCase):
    def test_cutoff_is_96_hours_and_late_mark_stays_at_48(self):
        self.assertEqual(w.STALE_HOURS, 48)
        self.assertEqual(w.STALE_SKIP_HOURS, 96)
        cand = item("森永乳業、新しいヨーグルトの研究成果を発表", 57)
        self.assertTrue(w.is_stale(cand))      # 48時間を超えたら late（ニュース用サイトマップ・速報に出さない）
        self.assertFalse(w.too_old(cand))      # でも見送らない
        self.assertTrue(w.too_old(item("森永乳業、新しいヨーグルトの研究成果を発表", 100)))
        self.assertFalse(w.is_stale(item("森永乳業、新しいヨーグルトの研究成果を発表", 40)))

    def test_live_events_keep_48_hours(self):
        for title in ("【復旧】一部サービスがご利用できない事象について", "台風の接近で計画運休　対象の路線",
                      "不正アクセスによる個人情報の漏えいについて"):
            self.assertTrue(w.live_event(item(title, 1)), title)
            self.assertTrue(w.too_old(item(title, 57)), title)
            self.assertEqual(w.stale_limit(item(title, 57)), 48, title)
        self.assertFalse(w.too_old(item("台風の接近で計画運休　対象の路線", 30)))

    def test_unknown_time_is_never_stale(self):
        cand = item("Figma、新機能を発表", 200, published_guessed=True)
        self.assertFalse(w.is_stale(cand))
        self.assertFalse(w.too_old(cand))

    def test_pipeline_wiring(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("elif not major and too_old(cand):", src)
        self.assertIn("if not major and too_old(item) and not (item.get(\"late\") and life_late_ok(item)):", src)
        self.assertIn("args.days = max(args.days, math.ceil(STALE_SKIP_HOURS / 24))", src)
        # 48時間を超えた発表は late の印（ニュース用サイトマップ・速報投稿に出さない）
        pick = src[src.index("    def _pick("):src.index("    def major_retry(")]
        self.assertIn('cand["late"] = True', pick)


if __name__ == "__main__":
    unittest.main()
