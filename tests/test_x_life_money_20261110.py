"""2026-11-10（台帳 S53）: X の投稿は暮らしとお金の「自分ごと」の記事を先に選ぶ。外部通信なし・何も投稿しない。

11/10 7:02 の X（速報）が「OpenAI、AIの研究ジョブを最大35秒で停止する「Control Room」」（AI・企業の話）だった。サイトの軸は
暮らしとお金で、AI の記事はほとんど読まれない。

  1. sns_plan.life_money: 暮らし・生活／社会・行政／投資・マネー／不動産と、流出・障害・値上げ・料金に当たるビジネス・ガジェットの記事。
     AI・企業向け（法人向け・読者が開発者や担当者）・海外の景気の数字は当たらない。地震・災害の知らせはいつも当たる
  2. X の枠: 暮らしとお金の記事 → 読者向けの文面 → Muse の図 → 点数＋人の閲覧（content/popular.json）。枠の時間に無ければ24時間以内の
     暮らしとお金の記事。それも無いときだけ AI・企業の記事
  3. X の枠の外の速報: 暮らしとお金の記事と災害の知らせだけ（AI の速報は出さない）
  4. ハッシュタグは話題の名前のタグを2〜3つまで（#年金 #給付金 など）。流出の記事に煽るタグを付けない。「｜」を使わない
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sns_plan  # noqa: E402
import sns_reader as sr  # noqa: E402
import sns_rules  # noqa: E402
import x_post as xp  # noqa: E402

NOW = datetime(2026, 11, 10, 3, 40, tzinfo=timezone.utc)  # 12:40 日本時間

OPENAI = {
    "slug": "openai-control-room-ai-workload-stop", "genreSlug": "ai", "breaking": True,
    "title": "OpenAI、AIの研究ジョブを最大35秒で停止する「Control Room」を導入　他の系が壊れても機能する設計",
    "tags": ["生成AI", "OpenAI", "AI安全", "LLM", "セキュリティ"], "sourceUrl": "https://openai.com/index/introducing-control-room",
    "verdict": {"audience": "AI安全に関心のある人"},
}
DOCOMO = {
    "slug": "docomo-leak", "genreSlug": "business", "title": "ドコモオンラインショップで個人情報が流出　最大約30万件",
    "tags": ["ドコモ", "情報流出"], "sourceUrl": "https://www.docomo.ne.jp/info/news/1.html",
}
PENSION = {
    "slug": "pension-support", "genreSlug": "public", "title": "年金生活者支援給付金は請求しないと始まらない　老齢は前年92万6,500円以下が対象",
    "tags": ["年金", "給付金"],
}
B2B = {
    "slug": "softbank-b2b", "genreSlug": "tech-gadget", "title": "法人向け回線は速度だけで選ばない　ソフトバンクが解説する5つのポイント",
    "verdict": {"audience": "企業のIT担当者"},
}
US_JOBS = {"slug": "us-jobs", "genreSlug": "business", "title": "米雇用者数16.5万人増、失業率は4.1%に低下　市場予想の7万人を大幅超え"}
HOKURIKU = {
    "slug": "hokulink-leak", "genreSlug": "ai", "title": "北陸電力の「ほくリンク」会員約55万件のメールアドレスが流出",
    "sourceUrl": "https://www.rikuden.co.jp/press/1.html",
}
QUAKE = {"slug": "quake", "genreSlug": "ai", "title": "【地震】石川県で震度5弱", "disaster": True}


def made(art: dict, minutes_ago: int) -> dict:
    return {**art, "generatedAt": (NOW - timedelta(minutes=minutes_ago)).isoformat()}


class LifeMoneyTest(unittest.TestCase):
    def test_classification(self):
        self.assertFalse(sns_plan.life_money(OPENAI))  # 11/10 7:02 の X
        self.assertTrue(sns_plan.life_money(DOCOMO))
        self.assertTrue(sns_plan.life_money(PENSION))
        self.assertFalse(sns_plan.life_money(B2B))
        self.assertFalse(sns_plan.life_money(US_JOBS))
        self.assertTrue(sns_plan.life_money(HOKURIKU))  # AI の分野に入った日本の一般のサービスの流出
        self.assertTrue(sns_plan.life_money(QUAKE))
        self.assertFalse(sns_plan.life_money({"slug": "s", "genreSlug": "sports", "title": "全日本卓球カデットが閉幕"}))
        self.assertTrue(sns_plan.b2b(B2B))
        self.assertTrue(sns_plan.foreign_macro(US_JOBS))
        self.assertFalse(sns_plan.foreign_macro(PENSION))


def fake_compose(article, link_at="reply"):
    return {"text": "x", "reply": "r", "kind": "reader", "style": "reader", "link": link_at}


class RankingTest(unittest.TestCase):
    def patches(self, figures=()):
        return [
            patch.object(xp.bp, "_indexable_rule", return_value=(lambda a, d: True, lambda arts: set())),
            patch.object(xp, "ok_for_x", return_value=True),
            patch.object(xp, "compose_post", side_effect=fake_compose),
            patch.object(xp, "figure_image", side_effect=lambda a: ("u", (1600, 900)) if a.get("slug") in figures else None),
            patch.object(xp, "popular_views", return_value={}),
        ]

    def run_with(self, fn, figures=()):
        ps = self.patches(figures)
        for p in ps:
            p.start()
        try:
            return fn()
        finally:
            for p in reversed(ps):
                p.stop()

    def test_life_money_first_even_if_ai_is_newer_and_scores_higher(self):
        ai = made({**OPENAI, "breaking": False, "title": "ChatGPTの料金プランが値下げ　月額20ドルから"}, 20)
        life = made(PENSION, 300)
        got = self.run_with(lambda: xp.candidates({}, {}, NOW, NOW - timedelta(hours=24), [ai, life]))
        self.assertEqual([a["slug"] for a in got][0], "pension-support")

    def test_figure_preferred_among_life_money(self):
        a = made(DOCOMO, 30)
        b = made(PENSION, 200)
        got = self.run_with(lambda: xp.candidates({}, {}, NOW, NOW - timedelta(hours=24), [a, b]), figures=("pension-support",))
        self.assertEqual(got[0]["slug"], "pension-support")

    def test_slot_reaches_back_24h_for_life_money_before_ai(self):
        ai = made({**OPENAI, "breaking": False}, 30)  # この枠の時間の中は AI の記事だけ
        life = made(DOCOMO, 20 * 60)  # 20時間前の暮らしの記事
        slot = sns_plan.x_slot_window(NOW)
        self.assertIsNotNone(slot)
        got = self.run_with(lambda: xp.slot_pick(slot, {}, {}, NOW, [ai, life]))
        self.assertEqual(got["slug"], "docomo-leak")
        # 暮らしとお金の記事が24時間に無いときだけ AI の記事
        got = self.run_with(lambda: xp.slot_pick(slot, {}, {}, NOW, [ai]))
        self.assertEqual(got["slug"], OPENAI["slug"])

    def test_breaking_outside_slots_skips_ai(self):
        ai = made(OPENAI, 10)
        life = made({**DOCOMO, "breaking": True}, 10)
        with patch.object(xp, "ok_for_x", return_value=True):
            got = xp.breaking_targets({}, {}, NOW, [ai, life])
        self.assertEqual([a["slug"] for a in got], ["docomo-leak"])

    def test_view_bonus_from_popular(self):
        views = {"pension-old": 82, "pension-support": 0}
        old = {"slug": "pension-old", "title": "年金の受け取りの手続き", "tags": ["年金"]}
        self.assertGreater(xp.view_bonus(PENSION, [old, PENSION], views), 0)  # 同じ話題（#年金）の記事が読まれている
        self.assertEqual(xp.view_bonus(B2B, [old, B2B], views), 0)
        self.assertLessEqual(xp.view_bonus({"slug": "pension-old", "title": "年金", "tags": []}, [old], {"pension-old": 10_000}),
                             xp.VIEW_BONUS_MAX)

    def test_popular_views_reads_file(self):
        import tempfile  # noqa: PLC0415

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            fh.write('{"items": [{"slug": "a", "views": 82}, {"slug": "b", "views": "x"}, {"views": 3}]}')
        self.assertEqual(xp.popular_views(Path(fh.name)), {"a": 82})
        self.assertEqual(xp.popular_views(Path(fh.name + ".missing")), {})


class TextTest(unittest.TestCase):
    def test_topic_tags_two_to_three(self):
        self.assertEqual(sns_plan.x_hashtags(PENSION), ["#年金", "#給付金"])
        heater = {"slug": "h", "genreSlug": "lifestyle", "title": "暖房の電気代、1時間いくら　こたつ約2.5円"}
        self.assertEqual(sns_plan.x_hashtags(heater), ["#電気代", "#暖房"])
        self.assertIn("#ニトリ", sns_plan.x_hashtags({"slug": "n", "genreSlug": "business", "title": "ニトリ会員情報、最大3,762万件流出の恐れ"}))
        leak = {"slug": "l", "genreSlug": "business", "title": "楽天カードを名乗る詐欺メールで流出"}
        self.assertNotIn("#詐欺", sns_plan.x_hashtags(leak))  # 流出の記事に煽るタグを付けない（S35）
        self.assertEqual(sns_plan.x_hashtags(QUAKE)[:1], sns_plan.x_hashtags(QUAKE))  # 地震は災害のタグだけ
        self.assertLessEqual(len(sns_plan.x_hashtags({"title": "ドコモ PayPay NISA iDeCo 年金", "tags": []})), sns_plan.X_TAG_MAX)

    def test_tag_options_try_most_first(self):
        self.assertEqual(sr.tag_options("#a #b #c"), ["#a #b #c", "#a #b", "#a", ""])
        self.assertEqual(sr.tag_options(""), [""])

    def test_gate_allows_three_topic_tags_and_rejects_pipe(self):
        text = "年金生活者支援給付金は請求しないと始まらない\n前年の年金などが92万6,500円以下なら対象です。"
        tags = [v for v in sns_rules.check_xpost("x", text + "\n#年金 #給付金", text, PENSION) if "ハッシュタグ" in v]
        self.assertEqual(tags, [])
        self.assertTrue([v for v in sns_rules.check_xpost("x", text + "\n#年金 #給付金 #暮らし", text, PENSION) if "ハッシュタグ" in v])
        piped = text.replace("始まらない", "始まらない｜")
        self.assertTrue([v for v in sns_rules.check_xpost("x", piped, piped, PENSION) if "｜" in v])

    def test_classic_first_line_has_no_pipe(self):
        art = {**PENSION, "title": "年金生活者支援給付金｜請求しないと始まらない", "lede": "前年の年金などが92万6,500円以下の人が対象です。"}
        text = xp.x_text(art)
        self.assertTrue(text.startswith("年金生活者支援給付金　請求しないと始まらない"), text)
        self.assertNotIn("｜", text)


if __name__ == "__main__":
    unittest.main()
