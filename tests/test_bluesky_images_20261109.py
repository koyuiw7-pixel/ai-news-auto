"""2026-11-09 オーナー承認（台帳 S51）: Bluesky も Threads で人が来ている形にそろえる。外部通信なし・何も投稿しない。

  1. ふつうの記事の投稿は、暗いリンクカードではなく記事の画像（Muse の図 → 写真のカード）を app.bsky.embed.images で付ける
  2. 記事のリンク（utm_source=bluesky・reader_body）は本文の「続き（◯◯）→」の facet
  3. 読者向けの文面がある記事を、速報の次に必ず先に選ぶ
  4. 画像の無い記事（文字だけのカード・ロゴ）は出さない。Muse の図があれば写真が無くても出せる
  5. 読者向けの下書きに LLM の部品の名前（closing・label）が混ざったら使わない
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402,F401  unittest でも自動投稿のスイッチを戻したときの決まり（auto_post=true）で動かす（tests/conftest.py・2026-11-10）

import bluesky_post as bp  # noqa: E402
import sns_reader as sr  # noqa: E402
import sns_rules  # noqa: E402
import threads_reader as tr  # noqa: E402
import x_post as xp  # noqa: E402

ARTICLE = {
    "slug": "smbc-mail-leak-test",
    "title": "三井住友銀行のメール配信の委託先からアドレス22万7,216件が流出",
    "description": "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。",
    "body": "対象は7月1日〜10月31日に同行が送ったメールの宛先です。問い合わせ窓口と対象の見分け方を案内しています。",
    "genreSlug": "public",
    "_virtual": True,
    "thumbnail": "https://ai-tech-express.jp/img/smbc-mail-leak-test-0a1b2c3d.jpg", "imageCredit": {"kind": "stock"},
}
MAIN = (
    "三井住友銀行からメールを受け取っていた法人・個人事業主の人へ。\n\n"
    "メール配信の委託先から、宛先のメールアドレス22万7,216件が漏れました。\n"
    "対象は7月1日〜10月31日に同行が送ったメールの宛先です。\n\n"
    "自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。"
)


def state(main=MAIN):
    return {"posts": {ARTICLE["slug"]: {"main": main, "reply": tr.reply_text(ARTICLE["slug"], "対象の見分け方"), "label": "対象の見分け方",
                                        "form": "he", "ending": main.splitlines()[-1], "status": "draft", "version": tr.VERSION,
                                        "at": "2026-11-08T12:00:00+00:00"}}}


def png(w, h) -> bytes:
    raw = b"".join(b"\x00" + b"\x00" * (w * 3) for _ in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)  # noqa: E731
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class ImageTest(unittest.TestCase):
    def test_card_when_no_figure(self):
        with tempfile.TemporaryDirectory() as d, patch.object(xp, "FIG_DIR", Path(d)):
            pics = bp.post_images(ARTICLE)
        self.assertEqual([p["from"] for p in pics], ["card"])
        self.assertTrue(pics[0]["url"].split("?")[0].endswith("/card/smbc-mail-leak-test"))

    def test_muse_figure_first(self):
        with tempfile.TemporaryDirectory() as d, patch.object(xp, "FIG_DIR", Path(d)):
            (Path(d) / "smbc-mail-leak-test-fig1.png").write_bytes(png(160, 90))
            (Path(d) / "other-article-fig1.png").write_bytes(png(160, 90))  # ほかの記事の図は使わない
            pics = bp.post_images(ARTICLE)
            no_photo = dict(ARTICLE, thumbnail="", imageCredit={"kind": "card"})
            fig_only = bp.post_images(no_photo)
        self.assertEqual([p["from"] for p in pics], ["figure", "card"])
        self.assertTrue(pics[0]["url"].endswith("/fig/smbc-mail-leak-test-fig1.png"))
        self.assertEqual((pics[0]["width"], pics[0]["height"]), (160, 90))
        self.assertEqual([p["from"] for p in fig_only], ["figure"])  # 写真が無くても Muse の図で出せる

    def test_no_real_image_means_nothing(self):
        no_photo = dict(ARTICLE, thumbnail="", imageCredit={"kind": "card"})
        with tempfile.TemporaryDirectory() as d, patch.object(xp, "FIG_DIR", Path(d)):
            self.assertEqual(bp.post_images(no_photo), [])

    def test_record_uses_image_embed_and_link_facet(self):
        with patch.object(tr, "load_state", return_value=state()), tempfile.TemporaryDirectory() as d, patch.object(xp, "FIG_DIR", Path(d)):
            p = bp.plan_brief(ARTICLE)
        self.assertEqual(p["kind"], "reader")
        self.assertEqual(p["pictures"][0]["from"], "card")
        blob = {"$type": "blob", "ref": {"$link": "bafk"}, "mimeType": "image/jpeg", "size": 1000}
        rec = bp.build_record(p["text"], p["link"], p["title"], p["desc"], None, full_text=p["full_text"],
                              image={"blob": blob, "width": 1600, "height": 900, "alt": "写真"})
        self.assertEqual(rec["embed"]["$type"], "app.bsky.embed.images")
        self.assertEqual(rec["embed"]["images"][0]["aspectRatio"], {"width": 1600, "height": 900})
        self.assertEqual(rec["embed"]["images"][0]["image"], blob)
        link = next(f for f in rec["facets"] if f["features"][0]["$type"].endswith("#link"))
        self.assertIn("utm_source=bluesky", link["features"][0]["uri"])
        self.assertIn("utm_content=reader_body", link["features"][0]["uri"])
        shown = rec["text"].encode()[link["index"]["byteStart"]:link["index"]["byteEnd"]].decode()
        self.assertEqual(shown, "ai-tech-express.jp/articles/smbc-mail-leak-test")
        self.assertNotIn("｜", rec["text"])
        self.assertLessEqual(len(rec["text"]), 300)
        media = [{"type": "image", "url": p["pictures"][0]["url"], "width": 1600, "height": 900}]
        self.assertEqual(sns_rules.check_post("bluesky", rec["text"], media, ARTICLE, kind="reader", links=[p["link"]]), [])

    def test_without_image_keeps_link_card(self):
        rec = bp.build_record("本文", "https://ai-tech-express.jp/articles/a?utm_source=bluesky", "t", "d", None)
        self.assertEqual(rec["embed"]["$type"], "app.bsky.embed.external")

    def test_main_posts_with_uploaded_image(self):
        """本番の流れ: 画像を上げて images の埋め込みで出す（xrpc・ログインは差し替え）"""
        now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone(timedelta(hours=9)))
        blob = {"$type": "blob", "ref": {"$link": "bafk"}, "mimeType": "image/jpeg", "size": 1000}
        sent = {}

        def fake_create(session, record, p, media):
            sns_rules.enforce("bluesky", record["text"], media, p.get("gate"), source="test", kind=p.get("kind", "article"),
                              links=[p["link"]])
            sent["record"], sent["media"] = record, media
            return {"uri": "at://did:plc:me/app.bsky.feed.post/abc"}

        with tempfile.TemporaryDirectory() as d, \
                patch.object(xp, "FIG_DIR", Path(d)), \
                patch.object(tr, "load_state", return_value=state()), \
                patch.object(bp, "EXTRA_PATH", Path(d) / "extra.json"), \
                patch.object(bp.tp, "load_state", return_value={"posted": {}}), \
                patch.object(bp.tp, "save_state"), \
                patch.object(bp, "choose", return_value=[(ARTICLE["slug"], {"article": ARTICLE}, "brief")]), \
                patch.object(bp, "login", return_value={"did": "did:plc:me", "handle": "me", "accessJwt": "x"}), \
                patch.object(bp, "upload_thumb", side_effect=lambda s, urls, used: (used.append(urls[0]), blob)[1]), \
                patch.object(bp, "create_record", side_effect=fake_create), \
                patch.object(bp, "datetime") as dt, \
                patch.dict("os.environ", {"THREADS_MODE": "live", "SNS_RULES_NO_ISSUE": "1"}), \
                patch.object(sys, "argv", ["bluesky_post.py"]):
            dt.now.return_value = now
            dt.fromisoformat = datetime.fromisoformat
            bp.main()
            extra = json.loads((Path(d) / "extra.json").read_text())
        self.assertEqual(sent["record"]["embed"]["$type"], "app.bsky.embed.images")
        self.assertTrue(sent["media"][0]["url"].split("?")[0].endswith("/card/smbc-mail-leak-test"))
        self.assertEqual(extra[ARTICLE["slug"]]["style"], "reader")


class OrderTest(unittest.TestCase):
    def test_reader_ready_articles_first(self):
        now = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
        made = (now - timedelta(hours=2)).isoformat()
        other = dict(ARTICLE, slug="other-news-test", title="別の話題のお知らせ", generatedAt=made,
                     thumbnail="https://ai-tech-express.jp/img/other-news-test-0a1b2c3d.jpg")
        ready = dict(ARTICLE, generatedAt=(now - timedelta(hours=3)).isoformat())

        def score(article, platform, generated, state=None):
            return (9.0 if article["slug"] == "other-news-test" else 1.0, generated)  # 点数は読者向けの文面の無い方が高い

        with patch.object(tr, "load_state", return_value=state()), \
                patch.object(bp, "_indexable_rule", return_value=(lambda a, d=frozenset(): True, lambda a: set())), \
                patch.object(bp, "brief_lines", return_value=("事実の文です。", "変わることです。")), \
                patch.object(sr, "rank_key", side_effect=score), \
                patch.object(bp.tp.sns_plan, "excluded", return_value=""):
            got = bp.brief_candidates({"posted": {}}, {}, now, now - timedelta(hours=12), [other, ready])
        self.assertEqual([a["slug"] for a in got], ["smbc-mail-leak-test", "other-news-test"])


class LeakTest(unittest.TestCase):
    LEAKY = MAIN.replace("\n\n自分が", "\nclosing\n自分が対象かどうかの見分け方と問い合わせ先は記事にまとめています。\nlabel\n対象の見分け方\n\n自分が")

    def test_gate_and_reuse_reject_field_names(self):
        self.assertEqual(sns_rules.reader_field_leak(self.LEAKY), "closing")
        self.assertEqual(sns_rules.reader_field_leak(MAIN), "")
        self.assertTrue(any("部品の名前" in v for v in sns_rules.check_threads_reader("threads", self.LEAKY, state()["posts"][ARTICLE["slug"]]["reply"], ARTICLE)))
        with patch.object(tr, "load_state", return_value=state(self.LEAKY)):
            self.assertIsNone(sr.bluesky_post(ARTICLE))
            self.assertIsNone(sr.x_post(ARTICLE))

    def test_assemble_drops_leaked_parts(self):
        main = tr.assemble({"who_line": "子ども食堂を運営している人に関わる話です。",
                            "facts": ["財務省が備蓄食品の提供を始めました。\n申し込みは先着順です。\nclosing\n詳細は記事にまとめています。\nlabel\n申込案内"],
                            "closing": "詳細は記事の案内文にまとめています。"})
        self.assertNotIn("closing", main)
        self.assertNotIn("label", main)
        self.assertIn("申し込みは先着順です。", main)

    def test_pair_for_recomposes_leaky_draft(self):
        art = dict(ARTICLE)
        good = {"main": MAIN, "reply": "r", "label": "l", "form": "he", "ending": "e"}
        with patch.object(tr, "load_state", return_value=state(self.LEAKY)), \
                patch.object(tr, "compose", return_value=good) as comp, patch.object(tr, "remember"):
            self.assertEqual(tr.pair_for(art)["main"], MAIN)
        comp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
