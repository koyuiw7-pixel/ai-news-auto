"""2026-11-09 オーナー承認（台帳 S50）: X の投稿の形。1日15本の枠はそのまま、全部の投稿で
①記事に合う本物の画像を必ず付ける（Muse の説明の図 → 写真の載るカード。文字だけのカード・ロゴは使わない。無ければ次の記事・枠は出さない）
②本文にリンクを置かず、返信に「続き → URL」（utm_source=x） ③ハッシュタグはトレンドの言葉に当たる記事だけ1つ。
外部通信なし（Buffer を呼ばない）。"""
import struct
import sys
import tempfile
import zlib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import sns_plan  # noqa: E402
import sns_rules  # noqa: E402
import x_post as xp  # noqa: E402
from test_x_slots_20261106 import article, at, phone  # noqa: E402


def no_photo(slug="nophoto", made=None):
    # 文字だけのカードになる記事（画像なし・imageCredit.kind=card）
    return article(slug, "Galaxy S26、新色を11月20日に発売　税込4万9800円", made or at(9),
                   thumbnail="", imageCredit={"kind": "card"}, coverImage="")


def png(path, w, h):
    """Pillow を使わない小さな PNG（X のワークフローには Pillow が無い）"""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff" * (w * 3) for _ in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class ImageTest(unittest.TestCase):
    def test_card_with_real_photo_is_used(self):
        image = xp.x_image(phone())
        self.assertIsNotNone(image)
        self.assertEqual(image["from"], "card")
        self.assertIn("/card/pixel", image["url"])

    def test_text_only_card_is_never_used_and_article_is_skipped(self):
        a = no_photo()
        self.assertTrue(sns_rules.photo_problem(a))
        self.assertIsNone(xp.x_image(a))
        self.assertFalse(xp.ok_for_x(a, {}, {}, []))
        self.assertTrue(any("ルール24" in p for p in xp.problems(a, "本文", {"text": "本文", "reply": xp.reply_link(a), "kind": "xpost"})))

    def test_slot_picks_next_article_with_image(self):
        now = at(12, 40)
        arts = [no_photo(made=at(11)), phone(made=at(10))]
        with patch.object(xp.bp, "_indexable_rule", return_value=(lambda a, d: True, lambda arts: set())):
            found = xp.candidates({}, {}, now, at(0), arts)
        self.assertEqual([a["slug"] for a in found], ["pixel"])

    def test_slot_is_skipped_when_no_article_has_an_image(self):
        now = at(12, 40)
        with patch.object(xp.bp, "_indexable_rule", return_value=(lambda a, d: True, lambda arts: set())):
            self.assertEqual(xp.candidates({}, {}, now, at(0), [no_photo(made=at(11))]), [])

    def test_muse_figure_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            fig = Path(tmp)
            png(fig / "pixel-fig1.png", 160, 90)
            png(fig / "pixel-fig2.png", 80, 80)  # 16:9 でない図は使わない
            png(fig / "other-fig1.png", 160, 90)  # ほかの記事の図は使わない
            with patch.object(xp, "FIG_DIR", fig):
                image = xp.x_image(phone())
                self.assertEqual(image["from"], "figure")
                self.assertTrue(image["url"].endswith("/fig/pixel-fig1.png"))
                post = xp.build_input(phone(), "ch", text="Pixel 11、新色を発売。\n税込3万9800円です。")
                self.assertTrue(post["metadata"]["twitter"]["thread"][0]["assets"][0]["image"]["url"].endswith("/fig/pixel-fig1.png"))
                # 文字だけのカードの記事でも、その記事の図があれば図で出す
                self.assertEqual(xp.x_image(no_photo("pixel"))["from"], "figure")


class OrderTest(unittest.TestCase):
    def test_reader_style_goes_first(self):
        now = at(12, 40)
        arts = [phone("classic", made=at(11)), phone("reader", made=at(10))]

        def fake(a, state=None, link_at="reply"):
            if a["slug"] != "reader":
                return None
            return {"text": "x", "reply": "続き（確認手順）→ https://ai-tech-express.jp/articles/reader?utm_source=x", "label": "確認手順"}

        with patch.object(xp.bp, "_indexable_rule", return_value=(lambda a, d: True, lambda arts: set())), \
                patch.object(xp.sns_reader, "x_post", side_effect=fake), patch.object(xp, "problems", return_value=[]):
            found = xp.candidates({}, {}, now, at(0), arts)
        self.assertEqual([a["slug"] for a in found], ["reader", "classic"])


class LinkTest(unittest.TestCase):
    def test_main_has_no_link_and_reply_has_link_with_utm(self):
        a = phone()
        post = xp.compose_post(a)
        built = xp.build_input(a, "ch", post=post)
        main, reply = built["metadata"]["twitter"]["thread"]
        self.assertFalse(sns_rules.links_in(main["text"]))
        self.assertTrue(main["assets"], "画像が付いていない")
        self.assertTrue(reply["text"].startswith("続き"))
        self.assertIn("utm_source=x", reply["text"])
        self.assertIn("/articles/pixel", reply["text"])

    def test_link_in_main_is_rejected(self):
        a = phone()
        text = f"Pixel 11、新色を発売。\n税込3万9800円です。\n{xp.reply_link(a).split(' ')[-1]}"
        self.assertTrue(xp.problems(a, text, {"text": text, "reply": xp.reply_link(a), "kind": "xpost"}))


class TrendTagTest(unittest.TestCase):
    def tearDown(self):
        sns_plan.clear_x_trends()

    def test_no_tag_unless_trends_loaded(self):
        sns_plan.clear_x_trends()
        self.assertEqual(sns_plan.x_hashtag(phone()), "")

    def test_one_tag_when_title_matches_trend(self):
        trends = [{"title": "pixel 11", "traffic": 5000}, {"title": "天気", "traffic": 9000}]
        self.assertEqual(sns_plan.x_trend_tag(phone(), trends), "#Pixel")
        self.assertEqual(sns_plan.x_trend_tag(article("w", "日経平均が反発、5万円台に", at(9)), [{"title": "日経平均"}]), "#日経平均")
        self.assertEqual(sns_plan.x_trend_tag(phone(), [{"title": "ドコモ"}]), "")

    def test_loaded_trends_drop_old_and_gossip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
            fresh = (now - timedelta(hours=2)).isoformat()
            old = (now - timedelta(hours=30)).isoformat()
            path.write_text('{"items": [{"title": "Pixel", "seen_at": "%s"}, {"title": "日経平均", "seen_at": "%s"},'
                            ' {"title": "Galaxy", "seen_at": "%s", "gossip": true}]}' % (fresh, old, fresh), "utf-8")
            self.assertEqual(sns_plan.use_x_trends(path, now), 1)
            self.assertEqual(sns_plan.x_hashtag(phone()), "#Pixel")

    def test_gate_accepts_the_trend_tag(self):
        sns_plan._X_TRENDS = [{"title": "Pixel"}]
        a = phone()
        post = xp.compose_post(a)
        self.assertEqual(xp.problems(a, post["text"], post), [])


class FirstLineTest(unittest.TestCase):
    def test_price_notation_tax_is_not_a_keyword(self):
        # 2026-11-09 14時の X: 「【税】ポータブル電源AC180は税込5万9,292円から…」。「税込」の「税」が言葉に当たっていた
        a = article("power", "ポータブル電源AC180は税込5万9,292円から　非常食は1食約504円で比べる", at(9),
                    lede="BLUETTIのポータブル電源「AC180」はセール価格で税込59,292円です。容量は1,152Whです。")
        self.assertEqual(sns_plan.x_keyword(a), "ポータブル電源AC180")
        self.assertFalse(xp.first_line(a).startswith("【"))
        self.assertNotIn("【税】", xp.x_text(a))

    def test_real_tax_words_still_work(self):
        self.assertFalse(sns_plan.keyword_like("税", "税込", 1))
        self.assertFalse(sns_plan.keyword_like("税", "消費税が", 3))
        self.assertTrue(sns_plan.keyword_like("NISA", "NISAの", 4))


class VolumeTest(unittest.TestCase):
    def test_x_keeps_15_slots(self):
        with patch.dict("os.environ", {"SNS_PER_DAY": "", "X_PER_DAY": ""}):
            self.assertEqual(sns_plan.x_daily_cap(), 15)
            self.assertEqual(len(sns_plan.x_slots_jst()), 15)


if __name__ == "__main__":
    unittest.main()
