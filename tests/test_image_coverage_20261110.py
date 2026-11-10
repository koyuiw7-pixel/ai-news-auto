"""画像の無い記事の対策（2026-11-10 オーナー「画像がない記事が結構多いから対策しっかりね」・台帳 I9）"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import figure_cover  # noqa: E402
import image_coverage  # noqa: E402
import images  # noqa: E402
import muse_images  # noqa: E402
import muse_images_push  # noqa: E402
import noir_cover  # noqa: E402
import sns_rules  # noqa: E402

NOW = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)


def art(slug: str, minutes_ago: float = 120, **kw) -> dict:
    base = {"slug": slug, "title": "11月分の電気代は1,286円増　国の値引きが終わり、冬の支援は1月分から", "genre": "暮らし・生活",
            "genreSlug": "lifestyle", "tags": ["家計", "光熱費"], "layout": "noir", "thumbnail": "",
            "publishedAt": (NOW - timedelta(minutes=minutes_ago)).isoformat()}
    base.update(kw)
    return base


class KeywordPlanTest(unittest.TestCase):
    """LLM が 500/503・時間切れでも、題名・タグから検索語と場面を作れる"""

    def test_life_money_topics(self):
        plan = images.keyword_plan(art("a"))
        self.assertIn("electricity meter", plan["queries"])
        self.assertEqual(plan["category"], "price")
        self.assertTrue(plan["scenes"])
        self.assertEqual(plan["model"], "keywords")
        pension = images.keyword_plan(art("b", title="女性の年金受給者の65.1%は月10万円未満", tags=["年金"]))
        self.assertIn("pension book", pension["queries"])

    def test_us_is_not_rice_and_au_is_not_inside_words(self):
        plan = images.keyword_plan({"title": "米国の利下げで円高に", "tags": ["Claude"], "genreSlug": "investment"})
        self.assertNotIn("rice bag", plan["queries"])
        self.assertNotIn("smartphone in hand", plan["queries"])

    def test_quake_gets_no_query(self):
        plan = images.keyword_plan({"title": "震度5弱の地震　津波の心配なし", "tags": [], "genreSlug": "public"})
        self.assertEqual(plan["scenes"], [])

    def test_plan_for_falls_back_when_llm_fails_or_is_slow(self):
        with patch.object(images, "visual_plan", side_effect=RuntimeError("500 INTERNAL")):
            plan = images.plan_for(art("a"))
        self.assertEqual(plan["model"], "keywords")
        with patch.object(images, "PLAN_LLM_SECONDS", 1.0), patch.object(images, "visual_plan", side_effect=lambda *a, **k: time.sleep(5)):
            began = time.time()
            plan = images.plan_for(art("a"))
        self.assertLess(time.time() - began, 4)
        self.assertEqual(plan["model"], "keywords")

    def test_plan_for_skips_llm_when_no_ai_left(self):
        with patch.object(images, "visual_plan", side_effect=AssertionError("LLM を呼ばない")):
            plan = images.plan_for(art("a"), ai_left=False)
        self.assertEqual(plan["model"], "keywords")


class RobustnessTest(unittest.TestCase):
    def test_with_timeout(self):
        with self.assertRaises(TimeoutError):
            images.with_timeout(1.0, time.sleep, 5)
        self.assertEqual(images.with_timeout(2.0, lambda: 7), 7)

    def test_http_get_retries_5xx(self):
        calls = []

        def once(url, **kw):
            calls.append(url)
            if len(calls) < 3:
                raise urllib.error.HTTPError(url, 503, "busy", {}, None)
            return b"ok", "text/plain", url

        with patch.object(images, "_http_get_once", side_effect=once), patch.object(images.time, "sleep"):
            self.assertEqual(images.http_get("https://example.org/x", retries=2)[0], b"ok")
        self.assertEqual(len(calls), 3)
        with patch.object(images, "_http_get_once", side_effect=urllib.error.HTTPError("u", 404, "no", {}, None)):
            with self.assertRaises(urllib.error.HTTPError):
                images.http_get("https://example.org/x", retries=2)

    def test_ai_budget_goes_to_life_money_first(self):
        with patch.object(images, "ai_used_today", return_value=images.AI_DAILY_MAX - 5), patch.object(images, "image_tier", return_value=4):
            self.assertFalse(images.ai_allowed({"slug": "ai-news"}))
        with patch.object(images, "ai_used_today", return_value=images.AI_DAILY_MAX - 5), patch.object(images, "image_tier", return_value=2):
            self.assertTrue(images.ai_allowed({"slug": "pension"}))
        with patch.object(images, "ai_used_today", return_value=images.AI_DAILY_MAX):
            self.assertFalse(images.ai_allowed({"slug": "pension"}))

    def test_cover_tries_not_spent_while_ai_is_capped(self):
        article = art("a")
        with patch.object(images, "ai_allowed", return_value=False):
            noir_cover.ensure_cover(article)
        self.assertNotIn("coverTries", article)


class FigureCoverTest(unittest.TestCase):
    """図の表紙: 題名の言葉と数字だけ（数字を作らない）・切れない・写真ではない印"""

    def test_key_fact_uses_title_words_only(self):
        cases = {
            "11月分の電気代は1,286円増　国の値引きが終わり、冬の支援は1月分から": ("11月分の電気代", "1,286円", "増"),
            "女性の年金受給者の65.1%は月10万円未満　給付金は自分で請求が必要": ("女性の年金受給者", "65.1%", "月10万円未満"),
            "児童手当、所得に関係なく月1万〜3万円　対象かの確かめ方": ("所得に関係なく", "月1万〜3万円", ""),
        }
        for title, (label, number, after) in cases.items():
            fact = figure_cover.key_fact(title)
            self.assertEqual((fact["label"], fact["number"], fact["after"]), (label, number, after), title)
            for part in (fact["label"], fact["number"], fact["after"], fact["sub"]):
                self.assertIn(part, title)

    def test_key_fact_keeps_whole_numbers(self):
        # 2026-11-10: 「約3億5,000万件」が「約3億」、「毎月5円」が「月5円」（前の言葉は「12月から毎」）と切れた図が出ていた
        cases = {
            "上場企業の個人情報漏えい、約3億5,000万件で過去最多に　10月に大型事故が集中": ("上場企業の個人情報漏えい", "約3億5,000万件", "過去最多に"),
            "ガソリン補助、12月から毎月5円ずつ縮小へ　春先に向けて基準価格を引き上げ": ("12月から", "毎月5円", "ずつ縮小へ"),
            "年金は月6万9,308円に増額": ("年金", "月6万9,308円", "増額"),
            "トヨタの中間決算、営業利益2兆1,911億円で9.2%増": ("営業利益", "2兆1,911億円", "9.2%増"),
            "老齢は前年92万6,500円以下が対象": ("老齢は前年", "92万6,500円", "以下が対象"),
            "パナソニック電気しき毛布DB-U12Tの電気代は1時間約1円　こたつ・ホットカーペットとは条件の違う目安": ("パナソニック電気しき毛布DB-U12Tの電気代は1時間", "約1円", ""),
            "トヨタ、自社株買いの枠を1兆円から1.3兆円に": ("自社株買いの枠", "1兆円", "から1.3兆円に"),
        }
        for title, (label, number, after) in cases.items():
            fact = figure_cover.key_fact(title)
            self.assertEqual((fact["label"], fact["number"], fact["after"]), (label, number, after), title)
            self.assertIn(fact["number"], title)  # 数字は題名の文字のまま

    def test_stale_figures_are_redrawn_without_photo_search(self):
        title = "上場企業の個人情報漏えい、約3億5,000万件で過去最多に　10月に大型事故が集中"
        old = art("breach", title=title, thumbnail="https://ai-tech-express.jp/img/breach-figure-e76581d7.jpg",
                  imageCredit={"kind": "figure", "imageKind": "cover", "number": "約3億", "label": "上場企業の個人情報漏えい"})
        fresh = {**old, "imageCredit": {**old["imageCredit"], "number": "約3億5,000万件"}}
        self.assertTrue(images.figure_stale(old))
        self.assertFalse(images.figure_stale(fresh))
        self.assertFalse(images.figure_stale({**old, "imageCredit": {"kind": "ai"}}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "breach.json"
            with patch.object(images, "store", return_value=("https://ai-tech-express.jp/img/breach-figure-new.jpg", (1200, 630))):
                done = images.refresh_stale_figures([(path, old), (path, fresh)], {"dry_run": True}, images.Counter())
        self.assertEqual(done, 1)
        self.assertEqual(old["imageCredit"]["number"], "約3億5,000万件")
        self.assertEqual(old["thumbnail"], "https://ai-tech-express.jp/img/breach-figure-new.jpg")

    def test_dates_are_not_the_key_number(self):
        fact = figure_cover.key_fact("11月9日午後3時から手続き再開　ドコモでまだ使えない9項目")
        self.assertEqual(fact["number"], "")

    def test_render_size_and_long_titles(self):
        long = art("x", title="とても長い題名の記事で数字がない場合でも図の表紙の文字が枠からはみ出さないことを確かめるための見出しです　後半もかなり長く書いてあり二行に収まらないかもしれません")
        for article in (art("a"), long, art("c", genreSlug="ai", title="AIでデータ準備時間を83%短縮")):
            image = figure_cover.render(article)
            self.assertEqual(image.size, (1200, 630))
            # 明るい図版（暗い・空の表紙にしない）
            self.assertGreater(sum(image.convert("L").resize((40, 21)).getdata()) / (40 * 21), 150)

    def test_never_uses_vertical_bar(self):
        self.assertNotIn("｜", figure_cover.split_title("電気代｜11月分は1,286円増")[0])

    def test_use_figure_marks_illustration(self):
        article = art("electricity-x")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "electricity-x.json"
            with patch.object(images, "store", return_value=("https://ai-tech-express.jp/img/electricity-x-figure-abc.jpg", (1200, 630))):
                out = images.use_figure(path, article, {"dry_run": True, "previous_credit": {}, "previous_thumb": {}})
        self.assertEqual(out, "figure")
        self.assertEqual(article["imageCredit"]["kind"], "figure")
        self.assertEqual(article["imageCredit"]["imageKind"], "cover")
        self.assertEqual(images.use_figure(path, art("q", noPhoto=True), {"dry_run": True}), "none")

    def test_figure_cover_is_not_a_photo_for_sns_and_yields_to_muse(self):
        article = art("electricity-x", thumbnail="https://ai-tech-express.jp/img/electricity-x-figure-abc.jpg",
                      imageCredit={"kind": "figure", "imageKind": "cover"})
        self.assertIn("図の表紙", sns_rules.photo_problem(article))
        self.assertEqual(muse_images.photo_state({**article, "layout": ""}), "none")
        muse = {**article, "coverImage": "https://ai-tech-express.jp/img/electricity-x-muse-1.jpg", "coverCredit": {"kind": "ai", "model": "muse"}}
        self.assertEqual(sns_rules.photo_problem(muse), "")
        source = (ROOT / "lib" / "article-index.mjs").read_text("utf-8")
        self.assertIn('figureCover = kind === "figure" && credit.imageKind === "cover"', source)

    def test_figure_cover_is_off_until_owner_ok(self):
        flow = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("IMAGE_FIGURE_COVER: ${{ vars.IMAGE_FIGURE_COVER || '0' }}", flow)

    def test_retry_after_hours(self):
        old = {"imageCredit": {"kind": "figure", "imageKind": "cover", "at": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()}}
        new = {"imageCredit": {"kind": "figure", "imageKind": "cover", "at": datetime.now(timezone.utc).isoformat()}}
        with patch.object(images, "ai_used_today", return_value=0):
            self.assertTrue(images.figure_retry(old))
            self.assertFalse(images.figure_retry(new))


class CoverageWatchTest(unittest.TestCase):
    def test_counts_missing_after_an_hour(self):
        articles = [
            art("none-old", 90),
            art("none-new", 20),
            art("photo", 90, thumbnail="https://ai-tech-express.jp/img/photo-1.jpg", imageCredit={"kind": "official"}),
            art("logo", 90, thumbnail="https://ai-tech-express.jp/img/logo-1.jpg", imageCredit={"kind": "official", "imageKind": "logo"}),
            art("borrowed", 90, thumbnail="https://ai-tech-express.jp/img/other-1.jpg", imageCredit={"kind": "official"}),
            art("card", 90, imageCredit={"kind": "card"}),
            art("muse", 90, coverImage="https://ai-tech-express.jp/img/muse-1.jpg", coverCredit={"kind": "ai"}),
            art("figure", 90, thumbnail="https://ai-tech-express.jp/img/figure-x.jpg", imageCredit={"kind": "figure", "imageKind": "cover"}),
            art("quake", 90, noPhoto=True),
            art("old", 60 * 30),
        ]
        found = image_coverage.scan(articles, now=NOW)
        self.assertEqual(sorted(r["slug"] for r in found["missing"]), ["borrowed", "card", "logo", "none-old"])
        self.assertEqual(found["waiting"], ["none-new"])
        self.assertEqual(found["figure"], ["figure"])
        self.assertEqual(found["total"], 8)
        self.assertIn("画像の無い記事 4 本", image_coverage.summary_line(articles, now=NOW))

    def test_hourly_watch_is_wired(self):
        flow = (ROOT / ".github" / "workflows" / "broken_images.yml").read_text("utf-8")
        self.assertIn("python scripts/image_coverage.py --issue", flow)


class DriveDropTest(unittest.TestCase):
    """Google ドライブの サイソク連絡/images/<slug>.jpg を Muse の受け箱へ写す"""

    def test_pull_drive(self):
        with tempfile.TemporaryDirectory() as tmp:
            drive, inbox, seen = Path(tmp) / "drive", Path(tmp) / "inbox", Path(tmp) / "seen.json"
            drive.mkdir()
            old = time.time() - 600
            for name in ("electricity-x.jpg", "electricity-x-fig1.png", "notes.txt", ".hidden.jpg"):
                (drive / name).write_bytes(b"x" * 20)
                os.utime(drive / name, (old, old))
            (drive / "writing-now.jpg").write_bytes(b"x")
            copied = muse_images_push.pull_drive(drive, inbox, seen)
            self.assertEqual(sorted(copied), ["electricity-x-fig1.png", "electricity-x.jpg"])
            self.assertTrue((inbox / "electricity-x.jpg").exists())
            self.assertTrue((inbox / "electricity-x-fig1.png").exists())
            self.assertTrue((drive / "README.txt").exists())
            self.assertEqual(muse_images_push.pull_drive(drive, inbox, seen), [])  # 二度写さない
            # 置き直した（時刻が変わった）ものはもう一度写す
            os.utime(drive / "electricity-x.jpg", (old + 5, old + 5))
            self.assertEqual(muse_images_push.pull_drive(drive, inbox, seen), ["electricity-x.jpg"])


class LedgerTest(unittest.TestCase):
    def test_ledger_row(self):
        text = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertIn("| I9 |", text)
        self.assertIn("tests/test_image_coverage_20261110.py", text)


if __name__ == "__main__":
    unittest.main()
