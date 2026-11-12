"""公開した記事を ChatGPT で見直す Mac の仕事（2026-11-08 オーナー承認・台帳 A65）。ネット・LLM・git を使わない"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gpt_review as g  # noqa: E402

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
SOURCE = ("九州電力は2026年9月28日、新たな電気料金単価を発表しました。従量電灯B、契約電流30A、使用電力量250kWhの場合、"
          "旧料金6,876円、新料金7,243円で367円の増加です。2026年11月1日使用分から適用します。") * 3
BODY = ("従量電灯Bの家庭では、2026年11月1日の使用分から支払い額が月367円増えます。\n\n"
        "## 新しい料金\n\n九州電力は2026年9月28日に発表しました。詳しくは[九州電力の発表](https://www.kyuden.co.jp/press/a.html)を見てください。\n\n"
        "![料金表](https://example.jp/a.png)\n\n| 比べること | 旧 | 新 |\n| --- | --- | --- |\n| 支払額 | 6,876円 | 7,243円 |\n")


def article(**extra) -> dict:
    base = {
        "slug": "kyushu-test", "title": "九州電力の電気料金、標準家庭で月367円値上げへ", "seoTitle": "九州電力の新電気料金",
        "lede": "九州電力は、2026年11月1日の使用分から電気料金単価を引き上げます。標準的な家庭では月367円上がり7,243円になります。",
        "description": "九州電力は2026年11月1日使用分から電気料金を改定します。従量電灯B（30A・250kWh）の家庭では月367円の値上げです。",
        "body": BODY, "sourceUrl": "https://www.kyuden.co.jp/press/a.html", "model": "gemini-3.6-flash",
        "generatedAt": (NOW - timedelta(hours=2)).isoformat(), "affiliates": [{"id": "x"}], "thumbnail": "https://example.jp/t.jpg",
    }
    base.update(extra)
    return base


SOURCES = [{"url": "https://www.kyuden.co.jp/press/a.html", "text": SOURCE}]


class SkipTest(unittest.TestCase):
    def test_skips_muse_editorial_checked_and_reviewed(self):
        self.assertIn("Muse", g.skip_reason(article(writer="muse")))
        self.assertTrue(g.skip_reason(article(refreshMode="editorial")))
        self.assertTrue(g.skip_reason(article(review={"status": "ok", "reviewedBy": "編集部"})))
        self.assertTrue(g.skip_reason(article(gptReview={"reviewedBy": "gpt-6.1-terra"})))
        self.assertTrue(g.skip_reason(article(sourceUrl=None)))
        self.assertEqual(g.skip_reason(article()), "")
        self.assertEqual(g.skip_reason(article(review={"status": "fix"})), "")

    def test_candidates_pick_recent_unreviewed_light_models_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "content" / "articles"
            folder.mkdir(parents=True)
            rows = {
                "sonnet-new": article(slug="sonnet-new", model="anthropic-api:claude-sonnet-5-5", generatedAt=(NOW - timedelta(hours=1)).isoformat()),
                "haiku-old": article(slug="haiku-old", model="anthropic-api:claude-haiku-5-5", generatedAt=(NOW - timedelta(hours=5)).isoformat()),
                "gemini-new": article(slug="gemini-new", generatedAt=(NOW - timedelta(hours=1)).isoformat()),
                "too-fresh": article(slug="too-fresh", generatedAt=(NOW - timedelta(minutes=3)).isoformat()),
                "too-old": article(slug="too-old", generatedAt=(NOW - timedelta(days=5)).isoformat()),
                "muse": article(slug="muse", writer="muse"),
                "done": article(slug="done"),
                "failed-twice": article(slug="failed-twice"),
            }
            for slug, a in rows.items():
                (folder / f"{slug}.json").write_text(json.dumps(a, ensure_ascii=False), "utf-8")
            state = {"items": {"done": {"status": "reviewed"}, "failed-twice": {"status": "failed", "attempts": 2}}}
            picked = [a["slug"] for _, a in g.candidates(root, state, NOW, 6)]
            self.assertEqual(picked, ["gemini-new", "haiku-old", "sonnet-new"])
            self.assertEqual(len(g.candidates(root, state, NOW, 1)), 1)

    def test_source_urls_include_cited_sources(self):
        a = article(factSources=[{"url": "https://www.nta.go.jp/a.pdf"}, {"url": "https://www.kyuden.co.jp/press/a.html"}],
                    sources=[{"url": "https://www.meti.go.jp/b.html"}])
        self.assertEqual(g.source_urls(a), ["https://www.kyuden.co.jp/press/a.html", "https://www.nta.go.jp/a.pdf",
                                            "https://www.meti.go.jp/b.html"])


class SourceTest(unittest.TestCase):
    def test_any_unreadable_source_skips_the_article(self):
        def fetcher(url):
            if "bad" in url:
                raise TimeoutError("timed out")
            return SOURCE
        _, why = g.fetch_sources(["https://ok.jp/a", "https://bad.jp/b"], fetcher)
        self.assertIn("bad.jp", why)
        got, why = g.fetch_sources(["https://ok.jp/a"], fetcher)
        self.assertEqual(why, "")
        self.assertEqual(got[0]["text"], SOURCE)

    def test_review_one_skips_without_calling_chatgpt(self):
        def caller(prompt):
            raise AssertionError("ChatGPT を呼んではいけない")
        result = g.review_one(Path("x.json"), article(), NOW, fetcher=lambda u: (_ for _ in ()).throw(OSError("404")), caller=caller)
        self.assertEqual(result["status"], "skipped")


class ValidateTest(unittest.TestCase):
    def test_good_patch_passes_and_bars_are_replaced(self):
        data = {"changed": True, "title": "九州電力の電気料金｜標準家庭で月367円値上げ　11月1日使用分から",
                "lede": "九州電力の従量電灯Bで30A・月250kWhを使う家庭は、2026年11月1日の使用分から月の支払額が367円増えて7,243円になります。",
                "body": BODY.replace("## 新しい料金", "## 標準家庭は月367円増")}
        patch, problems = g.validate(article(), data, SOURCES)
        self.assertEqual(problems, [])
        self.assertNotIn("｜", patch["title"])
        self.assertEqual(set(patch), {"title", "lede", "body"})

    def test_rejects_numbers_not_in_article_or_sources(self):
        data = {"title": "九州電力の電気料金、標準家庭で月400円値上げへ"}
        _, problems = g.validate(article(), data, SOURCES)
        self.assertTrue(any("400" in p for p in problems), problems)
        data = {"lede": "九州電力は、2026年11月1日の使用分から電気料金を上げます。標準的な家庭では月３６７円上がり7,243円になり、手続きはいりません。"}
        self.assertEqual(g.validate(article(), data, SOURCES)[1], [])  # 全角の数字・桁区切りも同じ数字

    def test_rejects_disallowed_fields_links_images_and_headings(self):
        _, problems = g.validate(article(), {"slug": "new-slug", "thumbnail": "https://x.jp/b.png"}, SOURCES)
        self.assertTrue(any("欄" in p for p in problems))
        no_link = BODY.replace("[九州電力の発表](https://www.kyuden.co.jp/press/a.html)", "九州電力の発表")
        self.assertTrue(any("リンク" in p for p in g.validate(article(), {"body": no_link}, SOURCES)[1]))
        no_image = BODY.replace("![料金表](https://example.jp/a.png)", "")
        self.assertTrue(any("画像" in p for p in g.validate(article(), {"body": no_image}, SOURCES)[1]))
        slot = "### Claudeのプランと料金（公式の料金と円の目安）"
        a = article(body=BODY + f"\n{slot}\n\n| プラン | 料金 |\n| --- | --- |\n| Pro | 367円 |\n")
        self.assertTrue(any("見出し" in p for p in g.validate(a, {"body": BODY + "\n| プラン | 料金 |\n| --- | --- |\n| Pro | 367円 |\n"}, SOURCES)[1]))
        short = "九州電力は2026年9月28日に発表しました。[発表](https://www.kyuden.co.jp/press/a.html)![料金表](https://example.jp/a.png)"
        self.assertTrue(any("長さ" in p for p in g.validate(article(), {"body": short}, SOURCES)[1]))

    def test_shared_gate_blocks_advice_added_by_chatgpt(self):
        body = BODY + "\n今が買い時で、注目銘柄です。\n"
        problems = g.validate(article(), {"body": body}, SOURCES)[1]
        self.assertTrue(any("共通の門" in p for p in problems), problems)

    def test_seo_title_is_not_added_when_missing(self):
        a = article()
        a.pop("seoTitle")
        patch, problems = g.validate(a, {"seoTitle": "九州電力の電気料金　月367円値上げ"}, SOURCES)
        self.assertEqual((patch, problems), ({}, []))

    def test_apply_records_reviewer_and_keeps_other_fields(self):
        a = article()
        new = g.apply_patch(a, {"title": "九州電力の電気料金　標準家庭で月367円値上げ"}, {"notes": "題名を直した"}, NOW)
        self.assertEqual(new["gptReview"]["reviewedBy"], "gpt-6.1-terra")
        self.assertEqual(new["gptReview"]["before"]["title"], a["title"])
        self.assertEqual({k: v for k, v in new.items() if k not in ("title", "gptReview")},
                         {k: v for k, v in a.items() if k != "title"})

    def test_stale_search_title_is_removed_after_rewrite(self):
        # 2026-11-11 kyuden-discount-jan-mar-2027: 書き直しで本文から「手続き」が消え、searchTitle だけ古い言葉のまま残った
        ok = {**article(), "searchTitle": "九州電力の電気料金、標準家庭で月367円値上げ"}
        kept = g.apply_patch(ok, {"lede": ok["lede"] + "　"}, {}, NOW)
        self.assertEqual(kept["searchTitle"], ok["searchTitle"])  # 記事の言葉のままなら残す
        self.assertNotIn("searchTitle", kept["gptReview"])
        stale = {**article(), "searchTitle": "九州電力の電気料金　手続き不要で割引"}
        new = g.apply_patch(stale, {"lede": stale["lede"] + "　"}, {}, NOW)
        self.assertNotIn("searchTitle", new)
        self.assertIn("検索の題名", new["gptReview"]["searchTitle"])
        self.assertEqual(stale["searchTitle"], "九州電力の電気料金　手続き不要で割引")  # 元の記事は書き換えない


class ChatGPTTest(unittest.TestCase):
    def runner(self, answer: str, code: int = 0, stderr: str = ""):
        def run(cmd, **kwargs):
            self.assertIn("gpt-6.1-terra", cmd)
            self.assertIn("read-only", cmd)
            out = Path(cmd[cmd.index("-o") + 1])
            if answer:
                out.write_text(answer, "utf-8")
            return subprocess.CompletedProcess(cmd, code, "", stderr)
        return run

    def test_errors_and_usage_limits_stop_the_run(self):
        with self.assertRaises(g.ChatGPTStop):
            g.call_chatgpt("x", runner=self.runner("", 1, "ERROR: You've hit your usage limit. Try again in 3 hours."))
        with self.assertRaises(g.ChatGPTStop):
            g.call_chatgpt("x", runner=self.runner("You've hit your usage limit. Upgrade to Pro or try again later."))
        with self.assertRaises(g.ChatGPTStop):
            g.call_chatgpt("x", runner=self.runner(""))
        self.assertEqual(g.parse_answer(g.call_chatgpt("x", runner=self.runner('```json\n{"changed": false}\n```'))), {"changed": False})

    def test_review_one_end_to_end_with_fakes(self):
        answer = json.dumps({"changed": True, "title": "九州電力の電気料金、標準家庭は月367円値上げ　11月1日使用分から",
                             "fixes": [], "notes": "題名を直した"}, ensure_ascii=False)
        result = g.review_one(Path("x.json"), article(), NOW, fetcher=lambda u: SOURCE, caller=lambda p: answer)
        self.assertEqual(result["status"], "reviewed")
        self.assertEqual(set(result["patch"]), {"title"})
        bad = json.dumps({"changed": True, "title": "九州電力の電気料金、標準家庭は月999円値上げ"}, ensure_ascii=False)
        self.assertEqual(g.review_one(Path("x.json"), article(), NOW, fetcher=lambda u: SOURCE, caller=lambda p: bad)["status"], "failed")

    def test_prompt_carries_rules_article_and_sources(self):
        prompt = g.build_prompt(article(), SOURCES)
        for word in ("うそをつかない", "｜", "資料に無い事実", "九州電力の電気料金、標準家庭で月367円値上げへ", "kyuden.co.jp/press/a.html"):
            self.assertIn(word, prompt)
        self.assertNotIn("affiliates", prompt)


class LaunchdTest(unittest.TestCase):
    def test_plist_runs_every_30_minutes_from_ascii_path(self):
        text = g.plist_text()
        self.assertIn("<integer>1800</integer>", text)
        self.assertIn(g.LABEL, text)
        path = text.split("<string>/opt/homebrew/bin/python3</string>")[1].split("</string>")[0]
        self.assertTrue(path.isascii())

    def test_commit_message_ends_with_co_author(self):
        self.assertTrue(g.CO_AUTHOR.startswith("Co-Authored-By: Claude Opus 5.5"))
        source = (ROOT / "scripts" / "gpt_review.py").read_text("utf-8")
        self.assertIn('\\n\\n{CO_AUTHOR}"', source)
        self.assertNotIn("--force", source)
        self.assertIn('"pull", "--quiet", "--rebase"', source)


if __name__ == "__main__":
    unittest.main()
