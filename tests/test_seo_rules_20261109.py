"""2026-11-09 オーナー承認（台帳 A68）「検索順位3位以内になった記事の特徴に合わせてロジックを組む」。外部への通信なし。

1. 検索に表示のあったページは取り下げない・転送しない。転送するなら、転送先に元の記事の名前が入っていること
2. 重複は「同じ発表」ではなく「同じ疑問」で判定（とは・料金・比較・使い方・ニュースは別の記事。互いに結ぶ）
3. 新しい名前の「〜とは」は名前ごとに1本。題名の最初の20字と最初の1文に名前。ほかの記事の最初の1か所から結ぶ
4. 4〜10位・表示10回以上の記事を毎週、答えを先に書き直す（更新日時を進める・品質ゲートはそのまま）
5. 人物のページが「最新ニュース（0本）」のまま検索に出ない
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import canonical_names  # noqa: E402
import headline_normalize as hn  # noqa: E402
import indexnow  # noqa: E402
import quality  # noqa: E402
import retire_articles  # noqa: E402
import search_protected  # noqa: E402
import search_refresh  # noqa: E402
import sns_plan  # noqa: E402
import story  # noqa: E402

RESTORED = (
    "gpt-6-1-terra-sol-astra-comparison",
    "chatgpt-gpt-6-1-terra-plans-guide",
    "gpt-6-1-terra-github-copilot-guide",
    "typesafe-ai-jev-decision-making-model",
    "gemma-4-ple-architecture-explained-matome",
)


def article(slug):
    return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))


def retired():
    return json.loads((ROOT / "content" / "retired.json").read_text("utf-8"))["articles"]


class RedirectGuardTest(unittest.TestCase):
    def test_unrelated_target_is_refused(self):
        clock = {"title": "Googleが「Gemini 4 Argon」でスマート時計を自作するデモを公開", "body": "Gemini 4 Argon で時計を作った。"}
        ok, missing = search_protected.redirect_ok("Gemini 4 ArgonのExcelクローンは何ができる？", clock)
        self.assertFalse(ok)
        self.assertEqual(["Excel"], missing)
        ok, _ = search_protected.redirect_ok("Gemini 4 Argonが登場", clock)
        self.assertTrue(ok)

    def test_query_words_are_required_too(self):
        guide = {"title": "OpenAI「GPT-6 Astra」の機能を整理", "body": "GPT-6 Astra の Swarm ワークフロー"}
        self.assertTrue(search_protected.redirect_ok("「GPT-6 Astra」の実力", guide, "astra swarm")[0])
        self.assertFalse(search_protected.redirect_ok("「GPT-6 Astra」の実力", {"title": "GPT-6 Astra", "body": ""}, "astra swarm")[0])

    def test_quoted_name_matches_in_any_order(self):
        ple = {"title": "Gemma 4のPLE（レイヤー別埋め込み）とは", "body": ""}
        self.assertTrue(search_protected.redirect_ok("Google、Gemma 4に搭載した「レイヤー別埋め込み（PLE）」の技術仕様を公開", ple)[0])

    def test_apply_drops_redirect_without_the_name_and_follows_duplicates(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        arts = root / "articles"
        arts.mkdir()
        files = {
            "excel-demo": {"slug": "excel-demo", "title": "ArgonのExcelクローン", "body": ""},
            "argon-news": {"slug": "argon-news", "title": "Argonの発表", "body": "Argon"},
            "clock": {"slug": "clock", "title": "Argonで時計", "body": "Argon"},
            "roundup-dup": {"slug": "roundup-dup", "title": "10月のまとめ", "body": "Argon", "duplicateOf": "clock"},
        }
        for slug, data in files.items():
            (arts / f"{slug}.json").write_text(json.dumps(data), "utf-8")
        saved = (retire_articles.ARTICLES, retire_articles.RETIRED, retire_articles.ROOT, search_protected.protected_slugs)
        retire_articles.ARTICLES, retire_articles.RETIRED, retire_articles.ROOT = arts, root / "retired.json", root
        search_protected.protected_slugs = lambda *a, **k: set()
        try:
            retire_articles.apply({
                "excel-demo": {"reason": "creator-video", "title": "ArgonのExcelクローン", "redirect": "clock"},
                "argon-news": {"reason": "duplicate", "title": "Argonの発表", "redirect": "roundup-dup"},
            }, datetime(2026, 11, 20, tzinfo=timezone.utc))
        finally:
            retire_articles.ARTICLES, retire_articles.RETIRED, retire_articles.ROOT, search_protected.protected_slugs = saved
            store = json.loads((root / "retired.json").read_text("utf-8"))["articles"]
            tmp.cleanup()
        self.assertNotIn("redirect", store["excel-demo"])  # Excel の無い記事へは転送しない（410）
        self.assertEqual("clock", store["argon-news"]["redirect"])  # 検索に出さない重複の記事ではなく代表へ

    def test_pages_with_impressions_are_protected(self):
        tmp = tempfile.TemporaryDirectory()
        prot = Path(tmp.name) / "p.json"
        pos = Path(tmp.name) / "pos.json"
        prot.write_text(json.dumps({"articles": {"a": {"clicks": 1}}}), "utf-8")
        pos.write_text(json.dumps({"pages": {"b": {"impressions": 1, "query": "b とは"}, "c": {"impressions": 0}}}), "utf-8")
        try:
            self.assertEqual({"a", "b"}, search_protected.protected_slugs(prot, pos))
            self.assertEqual("b とは", search_protected.query_of("b", prot, pos))
        finally:
            tmp.cleanup()


class RealDataTest(unittest.TestCase):
    def test_every_redirect_target_is_live_and_has_the_name(self):
        for slug, entry in retired().items():
            target = entry.get("redirect")
            if not target:
                continue
            path = ROOT / "content" / "articles" / f"{target}.json"
            self.assertTrue(path.exists(), f"{slug} の転送先 {target} が無い")
            data = json.loads(path.read_text("utf-8"))
            self.assertFalse(data.get("duplicateOf"), f"{slug} の転送先 {target} が重複の印の記事")
            ok, missing = search_protected.redirect_ok(entry.get("title", ""), data, search_protected.query_of(slug))
            self.assertTrue(ok, f"{slug} → {target} に {missing} が無い")

    def test_wrong_redirects_from_the_report_are_gone(self):
        r = retired()
        self.assertNotIn("redirect", r["gemini-4-argon-excel-clone-demo"])  # Excel の話の無いスマート時計の記事へ転送していた
        self.assertEqual("typesafe-ai-jev-decision-making-model", r["jev-fastest-ai-realtime-decision"]["redirect"])
        self.assertEqual("gemma-4-ple-architecture-explained-matome", r["gemma-4-per-layer-embeddings-explained"]["redirect"])

    def test_restored_pages_are_live_protected_and_clean(self):
        r = retired()
        protected = search_protected.protected_slugs()
        for slug in RESTORED:
            a = article(slug)
            self.assertNotIn(slug, r)
            self.assertIn(slug, protected)
            self.assertTrue(a.get("restoredAt") and a.get("updatedAt"))
            self.assertTrue(sns_plan.excluded(a), "戻した記事は新着ではないので SNS に出さない")
            self.assertFalse(a.get("videoUrl") or a.get("duplicateOf"))
            self.assertNotIn("｜", a["title"])
            self.assertGreaterEqual(len(a["body"]), 2500)
            self.assertIn("出典：", a["body"])
            self.assertEqual(quality.every_path_problems(a), [], slug)
            self.assertEqual(hn.title_problems(a["title"]) + hn.click_problems(a), [], slug)
            self.assertIsNone(indexnow.publish_block_reason(a), slug)
            self.assertIsNone(indexnow.noindex_reason(a), slug)

    def test_terra_pages_answer_different_questions_and_link_each_other(self):
        roles = {story.page_role(article(s)["title"]) for s in RESTORED[:3]} | {story.page_role(article("openai-gpt-6-1-terra-announcement")["title"])}
        self.assertEqual({"compare", "pricing", "howto", "news"}, roles)
        for slug in (*RESTORED[:3], "openai-gpt-6-1-terra-announcement"):
            related = set(article(slug).get("relatedSlugs") or [])
            others = {*RESTORED[:3], "openai-gpt-6-1-terra-announcement"} - {slug}
            self.assertTrue(others <= related, f"{slug} が役割違いの記事と結ばれていない: {others - related}")

    def test_terra_prices_match_the_pricing_table(self):
        prices = json.loads((ROOT / "content" / "pricing" / "openai-api.json").read_text("utf-8"))["models"]
        first = {m["id"]: m for m in prices if "≤" in str(m.get("tier"))}
        self.assertEqual((1, 5), (first["gpt-6.1-terra"]["input"], first["gpt-6.1-terra"]["output"]))
        self.assertEqual((2, 10), (first["gpt-6.1-sol"]["input"], first["gpt-6.1-sol"]["output"]))
        self.assertEqual((10, 50), (first["gpt-6-astra"]["input"], first["gpt-6-astra"]["output"]))
        body = article("gpt-6-1-terra-sol-astra-comparison")["body"]
        self.assertIn("| 入力料金（100万トークン・入力27.2万トークン以下） | 1ドル | 2ドル | 10ドル |", body)
        self.assertIn("2026年11月9日更新", body)


class RoleDedupeTest(unittest.TestCase):
    def story_of(self, slug, title, url="https://openai.com/index/introducing-gpt-6-1-terra/", hours=0):
        at = (datetime(2026, 10, 26, tzinfo=timezone.utc) + timedelta(hours=hours)).isoformat()
        return story.Story({"slug": slug, "title": title, "sourceUrl": url, "generatedAt": at, "publishedAt": at, "genreSlug": "ai"})

    def test_roles(self):
        self.assertEqual("about", story.page_role("Work IQとは　料金はCopilot Creditsの従量課金、導入手順も"))
        self.assertEqual("compare", story.page_role("ローカルAI向きはどっち　Mac Studio（M5 Ultra）とRTX 5090を比較"))
        self.assertEqual("pricing", story.page_role("ChatGPTの新しいAI「GPT-6.1 Terra」は誰が使える？プラン別に整理"))
        self.assertEqual("howto", story.page_role("GitHub Copilotで「GPT-6.1 Terra」を使うには　対象は5つのプラン"))
        self.assertEqual("news", story.page_role("OpenAI、新AIモデル「GPT-6.1 Terra」を発表　API料金は半分、速度は3倍以上に"))

    def test_same_source_different_question_is_not_duplicate(self):
        news = self.story_of("news", "OpenAI、新AIモデル「GPT-6.1 Terra」を発表　API料金は半分")
        cmp_ = self.story_of("cmp", "「GPT-6.1 Terra」は何が違う？SolやAstraと料金・性能を比較", hours=5)
        again = self.story_of("again", "OpenAI、新AIモデル「GPT-6.1 Terra」を公開　料金は半分", hours=6)
        self.assertIsNone(story.same_story(cmp_, news, {}))
        self.assertEqual("同じ出典URL", story.same_story(again, news, {}))  # 同じ疑問（ニュース）どうしは今までどおり重複
        self.assertEqual("同じ出典URL", story.same_story(cmp_, news, {}, ignore_role=True))
        sib = story.siblings([news, cmp_, again], {})
        self.assertIn("cmp", sib["news"])
        self.assertIn("news", sib["cmp"])
        self.assertNotIn("again", sib.get("news", []))  # 同じ役割の記事は結ぶ相手ではなく重複


class CanonicalNameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(["Work IQ"], canonical_names.names_of({"title": "Work IQとは　料金はCopilot Creditsの従量課金"}))
        self.assertEqual(["PLE", "レイヤー別埋め込み"], canonical_names.names_of({"title": "Gemma 4のPLE（レイヤー別埋め込み）とは　仕組み"}))
        self.assertEqual([], canonical_names.names_of({"title": "OpenAI、新モデルを発表"}))

    def test_about_pages_follow_the_title_and_first_sentence_rule(self):
        for _, data in canonical_names.load_all():
            self.assertEqual([], canonical_names.about_problems(data), data["slug"])
        bad = {"title": "TypeSafe AIの判断用の新しいAIのJevとは　何か", "body": "TypeSafe AIは新しいモデルを出しました。"}
        self.assertEqual(2, len(canonical_names.about_problems(bad)))

    def test_link_first_mention_skips_headings_tables_and_links(self):
        body = "## Work IQとは\n\n| Work IQ | x |\n\n[Work IQ](https://x)の話。Work IQは便利。Work IQも。"
        out = canonical_names.link_first_mention(body, "Work IQ", "work-iq")
        self.assertIn("の話。[Work IQ](/articles/work-iq)は便利。Work IQも。", out)
        self.assertTrue(out.startswith("## Work IQとは\n\n| Work IQ | x |"))
        self.assertIsNone(canonical_names.link_first_mention(out, "Work IQ", "work-iq"))  # 2回目は足さない

    def test_short_names_need_context_and_later_about_pages_merge(self):
        tmp = tempfile.TemporaryDirectory()
        d = Path(tmp.name)
        rows = []
        for data in (
            {"slug": "ple", "title": "Gemma 4のPLE（レイヤー別埋め込み）とは　仕組み", "body": "PLEは、Gemma 4の仕組みです。", "publishedAt": "2026-10-01"},
            {"slug": "gemma-news", "title": "Gemma 4を公開", "body": "Gemma 4はPLEを使う。", "publishedAt": "2026-10-02"},
            {"slug": "other-ple", "title": "物理の試験PLEを公開", "body": "PLEは物理の試験です。", "publishedAt": "2026-10-03"},
            {"slug": "ple-again", "title": "Gemma 4のPLEとは　もう一度", "body": "PLEは仕組みです。", "publishedAt": "2026-10-04"},
        ):
            path = d / f"{data['slug']}.json"
            path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
            rows.append((path, data))
        try:
            added = canonical_names.link_all(rows)
            saved = {p.stem: json.loads(p.read_text("utf-8")) for p, _ in rows}
        finally:
            tmp.cleanup()
        self.assertIn("gemma-news", added)
        self.assertIn("[PLE](/articles/ple)", saved["gemma-news"]["body"])
        self.assertNotIn("other-ple", added)  # 同じ略称の別の物（Gemma の無い記事）は結ばない
        self.assertEqual("ple", saved["ple-again"]["duplicateOf"])  # 同じ名前の「とは」は1本だけ

    def test_wiring(self):
        auto = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("python scripts/canonical_names.py link --days 7", auto)
        self.assertIn("最初の20字以内", hn.TITLE_STYLE_PROMPT)


class SearchRefreshTest(unittest.TestCase):
    def test_pick_positions_4_to_10_with_10_impressions(self):
        tmp = tempfile.TemporaryDirectory()
        d = Path(tmp.name)
        for s in ("ok", "top3", "far", "few", "recent", "busy"):
            (d / f"{s}.json").write_text("{}", "utf-8")
        pages = {
            "ok": {"position": 8.9, "impressions": 196, "query": "ipa 漏えい"},
            "busy": {"position": 4.0, "impressions": 300},
            "top3": {"position": 2.0, "impressions": 500},
            "far": {"position": 14.6, "impressions": 118},
            "few": {"position": 6.0, "impressions": 9},
            "recent": {"position": 7.0, "impressions": 50},
            "gone": {"position": 7.0, "impressions": 50},
        }
        now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        state = {"refreshed": [{"slug": "recent", "at": (now - timedelta(days=3)).isoformat()}]}
        try:
            picked = [s for s, _ in search_refresh.pick(pages, now, state, d)]
        finally:
            tmp.cleanup()
        self.assertEqual(["busy", "ok"], picked)

    def test_stamp_moves_date_modified_and_focus_keeps_truth_rule(self):
        now = datetime(2026, 11, 16, 1, tzinfo=timezone.utc)
        new = search_refresh.stamp({"slug": "x", "title": "t"}, {"query": "honda rn0 価格", "position": 8.8, "impressions": 22}, now)
        self.assertEqual("2026-11-16T01:00:00+00:00", new["updatedAt"])
        self.assertEqual("t", new["title"])
        focus = search_refresh.focus_for({"query": "honda rn0 価格", "position": 8.8})
        self.assertIn("「honda rn0 価格」", focus)
        self.assertIn("資料に無いことは書かない", focus)
        self.assertEqual("", search_refresh.focus_for({"position": 8.8}))

    def test_weekly_on_monday_jst_in_the_rewrite_workflow(self):
        self.assertTrue(search_refresh.is_monday_jst(datetime(2026, 11, 15, 19, 50, tzinfo=timezone.utc)))  # 日本時間 月曜 4:50
        self.assertFalse(search_refresh.is_monday_jst(datetime(2026, 11, 16, 19, 50, tzinfo=timezone.utc)))
        wf = (ROOT / ".github" / "workflows" / "types_rewrite.yml").read_text("utf-8")
        self.assertIn("scripts/search_refresh.py --apply --weekly", wf)
        self.assertIn("git add state/search_refresh.json", wf)
        import inspect

        import rewrite_types

        self.assertIn("focus", inspect.signature(rewrite_types.rewrite).parameters)

    def test_positions_file_is_from_search_console(self):
        data = search_protected.load_positions()
        self.assertIn("Search Console", data.get("window", "") + data.get("_note", ""))
        pages = search_protected.positions_pages()
        self.assertGreaterEqual(len(pages), 40)
        for slug in pages:
            self.assertTrue((ROOT / "content" / "articles" / f"{slug}.json").exists(), slug)
        self.assertIn("ipa-personal-data-leak-countermeasures", [s for s, _ in search_refresh.pick(pages, datetime.now(timezone.utc))])


class PeoplePageTest(unittest.TestCase):
    def test_no_zero_count_heading_and_noindex_only_when_empty(self):
        page = (ROOT / "app" / "people" / "[slug]" / "page.tsx").read_text("utf-8")
        lib = (ROOT / "lib" / "people.ts").read_text("utf-8")
        self.assertIn("export function personPage", lib)
        self.assertIn("indexable: own.length + org.length > 0", lib)
        self.assertIn("...(a.keywords ?? [])", lib)
        # 「最新ニュース（0本）」の見出しは、人物の記事があるときだけ
        head = page.index("の最新ニュース（{articles.length}本）")
        self.assertIn("{articles.length > 0 && (", page[head - 200:head])
        self.assertIn("robots: { index: false, follow: true }", page)
        index = (ROOT / "app" / "people" / "page.tsx").read_text("utf-8")
        self.assertIn("personArticles(p).length > 0 ?", index)


if __name__ == "__main__":
    unittest.main()
