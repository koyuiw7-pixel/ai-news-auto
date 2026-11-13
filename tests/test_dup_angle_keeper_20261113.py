"""重複の印（duplicateOf）は「同じ出来事で同じ切り口」の記事だけ・代表はいちばん強いページ（2026-11-13 オーナー「とにかく数字」）。

きっかけ: Muse の「NVIDIA決算は11月18日朝、オルカンの4.8%に響く日」が、同じ出典URLというだけで、前日の自動記事
「NVIDIAのフアンCEOが即日退任」の重複にされ、canonical が薄い方へ向いて検索から外れていた。
医療費控除・ふるさと納税・火災予防の Muse の記事 4 本も、同じ公式のページが出典というだけで重複にされていた。
ネットワーク・LLM は使わない。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import story  # noqa: E402

BODY = "## 概要\n" + "本文" * 800
URL = "https://nvidianews.nvidia.com/news/nvidia-announces-ceo-transition"


def art(slug, title, hours=0, body=BODY, url=URL, **kw):
    at = f"2026-11-{12 + hours // 24:02d}T{hours % 24:02d}:00:00+00:00"
    base = {"slug": slug, "title": title, "sourceUrl": url, "generatedAt": at, "publishedAt": at, "genreSlug": "investment",
            "keywords": [], "body": body, "channelSlug": "nvidia"}
    base.update(kw)
    return base


def plan_of(*items):
    stories = [story.Story(x) for x in items]
    return story.plan(stories, story.doc_freq(stories))


RESIGN = "NVIDIAのフアンCEOが即日退任　後任はクレスCFOが暫定、決算は17日予定どおり"
EARNINGS = "NVIDIA決算は11月18日朝、オルカンの4.8%に響く日　CEO交代後の初決算"


class SameEventSameAngleTest(unittest.TestCase):
    def test_same_source_different_angle_is_not_a_duplicate(self):
        old = art("resign", RESIGN, keywords=["NVIDIA CEO退任", "後任CEO"])
        new = art("earnings", EARNINGS, hours=16, writer="muse", keywords=["NVIDIA決算", "オルカン NVIDIA比率"])
        self.assertEqual({}, plan_of(old, new))
        # サイトと IndexNow の予備の判定（lib/article-index.mjs の markDuplicates と同じ）でも重複にしない
        self.assertEqual(set(), indexnow.duplicate_slugs([old, new]))

    def test_real_muse_pairs_from_the_same_official_page(self):
        pairs = [("医療費控除　10万円の壁は所得200万円未満なら5パーセントに下がる", "医療費控除の明細書、領収書は出さず5年保管　人と病院ごとにまとめて書けます"),
                 ("ふるさと納税、寄附先が6団体以上なら確定申告が必要　特例の切り替え方", "ふるさと納税の受領証明書をなくしたら　確定申告は3月15日まで"),
                 ("設置10年で警報器は交換の目安　11月9日から秋の火災予防運動", "住宅火災の死者は約7割　秋の火災予防運動、今週やる点検3つ")]
        for first, second in pairs:
            with self.subTest(first=first):
                a = art("a", first, url="https://www.nta.go.jp/x", genreSlug="public", writer="muse")
                b = art("b", second, hours=20, url="https://www.nta.go.jp/x", genreSlug="public", writer="muse")
                self.assertEqual({}, plan_of(a, b))
                self.assertEqual(set(), indexnow.duplicate_slugs([a, b]))

    def test_same_source_same_angle_is_still_a_duplicate(self):
        a = art("a", "NVIDIAのフアンCEOが即日退任　後任はクレスCFOが暫定", body=BODY + "本文" * 100)
        b = art("b", "NVIDIAのフアンCEOが退任、後任は暫定でクレスCFO", hours=3)
        self.assertEqual({"b": ("a", "同じ出典URL")}, plan_of(a, b))
        self.assertEqual({"b"}, indexnow.duplicate_slugs([a, b]))

    def test_candidate_before_generation_still_matches_by_source_url(self):
        """生成前の候補は今までどおり出典 URL だけで見る（同じ発表から自動でもう1本作らない）"""
        old, cand = story.Story(art("resign", RESIGN)), story.Story(art("", "NVIDIA Announces CEO Transition", hours=2))
        self.assertEqual("同じ出典URL", story.same_story(cand, old, {}, candidate=True))

    def test_different_dates_in_titles_are_different_events(self):
        a = story.Story(art("a", "GPT-7 Nova を11月5日に公開　料金は据え置き", url="https://openai.com/index/a", genreSlug="ai", keywords=["GPT-7 Nova", "OpenAI"]))
        b = story.Story(art("b", "GPT-7 Nova の日本での提供は11月19日から　料金は据え置き", hours=5, url="https://openai.com/index/b", genreSlug="ai",
                            keywords=["GPT-7 Nova", "OpenAI"]))
        self.assertTrue(story.date_conflict(a, b))
        self.assertIsNone(story.same_story(b, a, {}))
        same_day = story.Story({**b.data, "title": "GPT-7 Nova は5日に公開　料金は据え置き"})
        self.assertFalse(story.date_conflict(a, same_day))
        self.assertIsNotNone(story.same_story(same_day, a, {}))
        # 期間（3日間・15日以内）は日付として数えない
        self.assertEqual(set(), story.title_dates("申請は出生から15日以内　3日間の休みが対象"))
        self.assertEqual({(11, 18), (0, 17)}, story.title_dates("決算は11月18日朝、退任は17日"))


class StrongerKeeperTest(unittest.TestCase):
    A = "NVIDIAのフアンCEOが即日退任　後任はクレスCFOが暫定"
    B = "NVIDIAのフアンCEOが退任、後任は暫定でクレスCFO"

    def test_muse_article_is_the_keeper_even_when_newer_and_shorter(self):
        auto = art("auto", self.A, body=BODY + "本文" * 200)
        muse = art("muse", self.B, hours=10, writer="muse")
        self.assertEqual({"auto": ("muse", "同じ出典URL")}, plan_of(auto, muse))

    def test_then_longer_body_then_more_sources_then_newer(self):
        short, long_ = art("short", self.A), art("long", self.B, hours=5, body=BODY + "本文" * 200)
        self.assertEqual({"short": ("long", "同じ出典URL")}, plan_of(short, long_))
        one = art("one", self.A)
        two = art("two", self.B, hours=5, updates=[{"sourceUrl": "https://nvidianews.nvidia.com/news/second"}])
        self.assertEqual({"one": ("two", "同じ出典URL")}, plan_of(one, two))
        older, newer = art("older", self.A), art("newer", self.B, hours=5)
        self.assertEqual({"older": ("newer", "同じ出典URL")}, plan_of(older, newer))

    def test_article_with_search_impressions_stays_the_keeper(self):
        """検索に表示があった記事は代表のまま（台帳 A46・A68「転送しない」）"""
        auto, muse = art("auto", self.A), art("muse", self.B, hours=10, writer="muse")
        with patch.object(story, "_search_protected", return_value={"auto"}):
            self.assertEqual({"muse": ("auto", "同じ出典URL")}, plan_of(auto, muse))

    def test_article_that_is_noindex_for_another_reason_is_not_the_keeper(self):
        empty = art("empty", self.A, body="短い", writer="muse")
        full = art("full", self.B, hours=5)
        self.assertEqual({"empty": ("full", "同じ出典URL")}, plan_of(empty, full))

    def run_mark(self, items, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            for d in items:
                (Path(tmp) / f"{d['slug']}.json").write_text(json.dumps(d, ensure_ascii=False), "utf-8")
            with patch.object(story, "ARTICLES_DIR", Path(tmp)), patch.object(story, "_search_protected", return_value=set()):
                story.mark(**kw)
            return {p.stem: json.loads(p.read_text("utf-8")) for p in Path(tmp).glob("*.json")}

    def test_mark_moves_the_canonical_to_the_new_stronger_article(self):
        """強い記事が後からできたら、その記事を代表にして、前の代表と、前の代表を指していた印を付け替える"""
        auto = art("auto", self.A)
        copy = art("copy", "NVIDIAのフアンCEOが即日退任　後任は暫定", hours=1, body="## 概要\n" + "本文" * 300, duplicateOf="auto", duplicateReason="同じ出典URL")
        muse = art("muse", self.B, hours=10, writer="muse")
        saved = self.run_mark([auto, copy, muse])
        self.assertNotIn("duplicateOf", saved["muse"])
        self.assertEqual("muse", saved["auto"]["duplicateOf"])
        self.assertEqual("muse", saved["copy"]["duplicateOf"])  # 重複の記事（auto）へ canonical を向けたままにしない

    def test_recompute_removes_wrong_marks_but_keeps_hand_made_ones(self):
        resign = art("resign", RESIGN)
        earnings = art("earnings", EARNINGS, hours=16, writer="muse", duplicateOf="resign", duplicateReason="同じ出典URL")
        by_hand = art("by-hand", "ドコモ障害は5G SA契約者だけが対象", hours=20, url="https://www.docomo.ne.jp/x", duplicateOf="resign")
        saved = self.run_mark([resign, earnings, by_hand], recompute=True)
        self.assertNotIn("duplicateOf", saved["earnings"])
        self.assertEqual("resign", saved["by-hand"]["duplicateOf"])  # 手で付けた印（理由なし）は外さない

    def test_js_fallback_uses_the_same_threshold(self):
        js = (ROOT / "lib" / "article-index.mjs").read_text("utf-8")
        self.assertIn(f"export const SAME_URL_TITLE_SIM = {indexnow.SAME_URL_TITLE_SIM};", js)
        self.assertEqual(indexnow.SAME_URL_TITLE_SIM, story.SAME_URL_SIM)


if __name__ == "__main__":
    unittest.main()
