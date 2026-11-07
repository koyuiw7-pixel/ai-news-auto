"""2026-11-07 夜 オーナー承認（台帳 A57）: 1日の記事の6割以上を、日本の暮らし・お金・手続き・値上げ・障害・リコール・
詐欺/情報流出・税と給付の話題にする。1日の本数は減らさない（並び・発信元・暮らし・お金の公式の発表を拾う期間で寄せる）。
外部への通信なし。"""

import json
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import discover_pick  # noqa: E402
import feeds  # noqa: E402
import news_mix as nm  # noqa: E402
import web_articles as w  # noqa: E402

JST = timezone(timedelta(hours=9))
NEW_FEEDS = {"meti-press", "docomo-notice", "aeon", "chuden", "rakuten-card"}
PRESS_HOSTS = re.compile(r"nhk\.or\.jp|yahoo\.co\.jp|asahi\.com|yomiuri|mainichi|nikkei\.com|sankei|kyodo|jiji\.com|itmedia|impress")


class LifeShareConfigTest(unittest.TestCase):
    def test_life_group_is_at_least_sixty_percent(self):
        cfg = json.loads((ROOT / "scripts" / "news_mix.json").read_text("utf-8"))
        group = set(cfg["life_group"])
        self.assertEqual(group, {"alert", "money", "life"})
        self.assertGreaterEqual(cfg["life_min_share"], 0.6)
        self.assertGreaterEqual(round(sum(cfg["categories"][g]["share"] for g in group), 2), 0.6)
        # 海外の企業向け・開発者向けは今までどおり1日2本まで
        self.assertEqual(nm.cap_of("enterprise_dev"), 2)

    def test_life_behind(self):
        self.assertTrue(nm.life_behind({}))
        self.assertTrue(nm.life_behind({"alert": 2, "money": 3, "enterprise_dev": 17, "other": 16}))
        self.assertFalse(nm.life_behind({"alert": 3, "money": 2, "life": 1, "brand": 4}))


class ClassifyLifeTest(unittest.TestCase):
    def test_life_topics(self):
        cases = [
            ("【復旧】楽天モバイルの一部サービスがご利用できない事象について", "rakuten-mobile-info", "alert"),
            ("北陸電力会員サービス「ほくリンク」会員のメールアドレス外部流出について", "rikuden", "alert"),
            ("【注意喚起】ドコモのUSJキャンペーンを装った偽メール・偽サイトにご注意ください", "docomo-notice", "alert"),
            ("マイナ保険証の利用登録の解除申請、受付開始", "mhlw", "money"),
            ("忘年会シーズン到来　博多発23時台に臨時列車運行", "jrkyushu", "life"),
            ("高病原性鳥インフルエンザの発生・感染報告状況", "maff-tori", "life"),
        ]
        for title, slug, want in cases:
            self.assertEqual(nm.classify({"title": title, "source_slug": slug}), want, title)

    def test_product_security_features_stay_out_of_alert(self):
        self.assertNotEqual(nm.classify({"title": "Google、10月のAI発表まとめ　詐欺対策も", "source_slug": "google-blog-all"}), "alert")
        self.assertNotEqual(nm.classify({"title": "情報漏えいを防ぐ新サービスを提供開始", "source_slug": "x"}), "alert")

    def test_life_first_when_behind(self):
        counts = {"enterprise_dev": 2, "other": 10, "ai_consumer": 5}
        life = {"title": "児童手当の申請方法と対象者　11月から受付開始", "source_slug": "cfa-news"}
        ai = {"title": "ChatGPT、無料プランでも画像生成が使えるように", "source_slug": "openai-news"}
        ranked = sorted([ai, life], key=lambda i: nm.order_key(i, counts))
        self.assertEqual(ranked[0], life)


class LaneOrderTest(unittest.TestCase):
    def test_ai_lane_moves_behind_broad_lanes_when_life_is_behind(self):
        lanes = {"ai": [1], "public": [1], "lifestyle": [1], "sports": [1]}
        now = datetime(2026, 11, 7, 20, tzinfo=JST)
        self.assertEqual(w.lane_order(lanes, now)[0], "ai")
        order = w.lane_order(lanes, now, ai_last=True)
        self.assertEqual(order[-1], "sports")
        self.assertEqual(order[-2], "ai")
        self.assertEqual(sorted(order), sorted(lanes), "レーンは減らさない（本数を減らさない）")

    def test_pipeline_uses_life_behind(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("ai_last=news_mix.life_behind(mix_counts)", src)
        self.assertIn("life_late_ok(cand)", src)


class LifeLateTest(unittest.TestCase):
    def _item(self, title, hours, slug="nta-news"):
        return {"title": title, "source_slug": slug, "lang": "ja",
                "published_at": datetime.now(timezone.utc) - timedelta(hours=hours)}

    def test_money_and_procedures_can_be_late(self):
        self.assertTrue(w.life_late_ok(self._item("飲食料品の消費税率、2027年4月から1%に　届出の特例も", 72)))
        self.assertTrue(w.life_late_ok(self._item("年末年始の臨時列車　博多発の増発", 80, "jrkyushu")))
        # 台風・障害のような「いま起きている」話題は48時間まで（late にしない）
        self.assertFalse(w.life_late_ok(self._item("台風の接近で計画運休　対象の路線", 80, "jrwest")))

    def test_too_old_outages_and_foreign_are_not_late(self):
        self.assertFalse(w.life_late_ok(self._item("消費税率の特例の届出", w.LIFE_LATE_HOURS + 5)))
        self.assertFalse(w.life_late_ok(self._item("【復旧】一部サービスがご利用できない事象について", 72, "rakuten-mobile-info")))
        foreign = self._item("New pricing for the API", 72, "aws-news-blog")
        foreign["lang"] = "en"
        self.assertFalse(w.life_late_ok(foreign))


class NewFeedsTest(unittest.TestCase):
    def test_new_official_feeds(self):
        by_slug = {f["slug"]: f for f in feeds.BROAD_FEEDS}
        self.assertTrue(NEW_FEEDS <= set(by_slug), sorted(NEW_FEEDS - set(by_slug)))
        for slug in NEW_FEEDS:
            f = by_slug[slug]
            self.assertEqual(f["lang"], "ja", slug)
            self.assertIn(f["kind"], ("gov", "company"), slug)
            self.assertNotRegex(f["url"], PRESS_HOSTS, slug)
            for key in ("include_re", "exclude_re", "link_re"):
                if f.get(key):
                    re.compile(f[key])
        slugs = [f["slug"] for f in feeds.FEEDS + feeds.BROAD_FEEDS]
        self.assertEqual(len(slugs), len(set(slugs)), "slug は重ならない")


class DiscoverPickTest(unittest.TestCase):
    def setUp(self):
        import indexnow

        # 検索に出すかの判定（本文・主題）は indexnow の役目。ここでは Discover の決まりだけを見る
        self._patch = patch.object(indexnow, "noindex_reason", lambda article: "thin" if article.get("slug") == "noindex" else None)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _a(self, slug, title, **kw):
        base = {"slug": slug, "title": title, "generatedAt": "2026-11-07T03:00:00+00:00",
                "coverImage": f"https://ai-tech-express.jp/img/{slug}-cover.jpg", "qualityScore": 90,
                "sourceUrl": "https://www.nta.go.jp/x", "channelSlug": "nta-news",
                "body": "## 何が変わるか\n\n" + "国税庁は、飲食料品の消費税率を2027年4月から2年間1%にすると案内しました。対象の事業者は届出の特例を使えます。" * 40}
        base.update(kw)
        return base

    def test_rules(self):
        ok = self._a("a", "飲食料品の消費税率、2027年4月から1%に")
        self.assertIsNone(discover_pick.problem(ok))
        self.assertIsNotNone(discover_pick.problem(self._a("b", "消費税率の特例について")))  # 数字なし
        self.assertIsNotNone(discover_pick.problem(self._a("c", "衝撃！値上げは3割")))  # あおり
        self.assertIsNotNone(discover_pick.problem(self._a("d", "値上げは3割｜今週のまとめ")))  # 「｜」
        self.assertIsNotNone(discover_pick.problem(self._a("e", "値上げは3割", coverImage="", thumbnail="")))  # 大きな画像なし
        self.assertIsNotNone(discover_pick.problem(self._a("f", "値上げは3割", late=True)))
        self.assertIsNotNone(discover_pick.problem(self._a("noindex", "値上げは3割")))  # 検索に出さない記事

    def test_daily_limit(self):
        now = datetime(2026, 11, 7, 20, tzinfo=JST)
        arts = [self._a(f"s{i}", f"料金を{i + 1}%値上げ") for i in range(9)]
        marked, new = discover_pick.pick(arts, now=now, limit=5)
        self.assertEqual(len(marked) + len(new), 5)
        arts[0]["discoverCandidate"] = True
        marked, new = discover_pick.pick(arts, now=now, limit=5)
        self.assertEqual((len(marked), len(new)), (1, 4))

    def test_workflow_runs_it(self):
        wf = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("python scripts/discover_pick.py", wf)


if __name__ == "__main__":
    unittest.main()
