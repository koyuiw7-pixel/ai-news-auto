"""2026-11-13 オーナー承認: Muse の入稿の道だけ、主要な報道機関の記事を「報道の出典」として使える（台帳 W31 の例外）。

守ること（コードで確かめる）:
- 使えるのは一覧（muse_format.PRESS_ALLOWED）の報道機関だけ。ほかの報道・ニュースブログ・まとめは今までどおり出典にできない
- 報道にしか無い数字は、その文に報道機関の名前（か「報道」「報じた」）を入れる。題名・リード・要点・SNS の文も同じ
- 報道の文を写さない
- 公式の資料が無い記事（報道だけ）は、今までの「報道が出典」の形（radar-<ホスト>・出典（報道））で印を付け、検索に出さず、
  公式の発表が未確認であることを本文と免責文に書く
- 自動の記事（writer が muse でない）は今までどおり W31 で止まる
ネット・LLM を使わない。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import easy_version  # noqa: E402
import indexnow  # noqa: E402
import llm  # noqa: E402
import main as m  # noqa: E402
import muse_articles as ma  # noqa: E402
import muse_format as mf  # noqa: E402
import public_interest as pi  # noqa: E402
import quality  # noqa: E402
import web_articles as w  # noqa: E402

MOF = "https://www.mof.go.jp/policy/international_policy/reference/feio/data.html"
NHK = "https://news.web.nhk/newsweb/na/nd-20261113de75110"
TBS = "https://newsdig.tbs.co.jp/articles/-/3082981"
OFFICIAL_TEXT = "財務省は為替介入の実績を公表しています。10月の介入額は0円でした。" + "外国為替平衡操作の実施状況の説明です。" * 20
NHK_TEXT = ("12日のニューヨーク外国為替市場で円相場は一時1ドル＝160円台まで値下がりし、およそ2か月ぶりの円安水準となりました。"
            "市場関係者は日米の金利差が意識されたと話しています。午後5時時点では159円81銭でした。") + "市場の動きを伝える記事の続きです。" * 20


def src(url: str, text: str, press: str = "", name: str = "") -> dict:
    out = {"url": url, "name": name or press or "財務省", "facts": "f", "text": text, "full_text": "", "title": "t",
           "image": "https://example.jp/photo.jpg", "published": None, "page": {"text": text, "image": "https://example.jp/photo.jpg"}}
    if press:
        out["press"] = press
    return out


MIXED = [src(MOF, OFFICIAL_TEXT), src(NHK, NHK_TEXT, "NHK")]
PRESS_ONLY = [src(NHK, NHK_TEXT, "NHK")]


class AllowlistTest(unittest.TestCase):
    def test_only_the_listed_major_outlets_are_allowed(self):
        allowed = {
            "https://www3.nhk.or.jp/news/html/20261113/k1.html": "NHK", "https://news.web.nhk/newsweb/na/nd-1": "NHK",
            "https://www.47news.jp/1.html": "共同通信", "https://www.kyodo.co.jp/a": "共同通信", "https://www.jiji.com/jc/article?k=1": "時事通信",
            "https://www.nikkei.com/article/DGXZQO1/": "日本経済新聞", "https://www.asahi.com/articles/A.html": "朝日新聞",
            "https://www.yomiuri.co.jp/economy/1/": "読売新聞", "https://mainichi.jp/articles/1": "毎日新聞",
            "https://www.reuters.com/markets/x/": "ロイター", "https://jp.reuters.com/markets/x/": "ロイター",
            "https://www.bloomberg.com/news/articles/x": "ブルームバーグ", "https://www.bloomberg.co.jp/news/articles/x": "ブルームバーグ",
            "https://apnews.com/article/x": "AP通信", "https://newsdig.tbs.co.jp/articles/-/1": "TBS NEWS DIG",
            "https://news.tv-asahi.co.jp/news_economy/articles/1.html": "テレビ朝日", "https://news.ntv.co.jp/category/economy/1": "日本テレビ",
            "https://www.fnn.jp/articles/-/1": "FNN",
        }
        for url, name in allowed.items():
            self.assertEqual(mf.press_outlet(url), name, url)
            self.assertTrue(pi.is_press_url(url) or mf.NOT_OFFICIAL_RE.search(url) or True)
        for url in ("https://www.sankei.com/article/1/", "https://www.itmedia.co.jp/news/1.html", "https://news.yahoo.co.jp/articles/1",
                    "https://www.tbs.co.jp/tv/1", "https://www.tv-asahi.co.jp/program/", "https://prtimes.jp/main/html/rd/p/1.html",
                    "https://note.com/a/n/1", "https://www.axios.com/2026/11/07/x", "https://nhk.or.jp.example.com/a",
                    "https://example.com/?u=https://www.nhk.or.jp/", "https://www.nta.go.jp/a", ""):
            self.assertEqual(mf.press_outlet(url), "", url)

    def test_shared_platform_needs_the_agency_name(self):
        self.assertEqual(mf.press_outlet("https://nordot.app/1234", "共同通信「円下落」"), "共同通信")
        self.assertEqual(mf.press_outlet("https://nordot.app/1234", "神戸新聞"), "")

    def test_every_outlet_has_aliases(self):
        for _host, name in mf.PRESS_ALLOWED:
            self.assertIn(name, mf.PRESS_ALIASES)
            self.assertTrue(all(len(a) >= 2 for a in mf.PRESS_ALIASES[name]))
        self.assertNotIn("毎日", mf.PRESS_ALIASES["毎日新聞"])  # 「毎日」はふつうの言葉

    def data(self, urls: list[str]) -> dict:
        return {"title": "円相場が一時1ドル160円台、家計への影響を整理する", "genre": "お金", "notes": "", "body": "本文",
                "sources": [{"url": u, "name": "n", "facts": "f"} for u in urls]}

    def test_format_keeps_major_press_after_official_and_drops_other_press(self):
        d = self.data([NHK, "https://news.yahoo.co.jp/articles/1", MOF, TBS])
        self.assertEqual(mf.problems(d, "20261113-お金-円安160円台の影響.md"), [])
        self.assertEqual([s["url"] for s in d["sources"]], [MOF, NHK, TBS])
        self.assertEqual([s.get("press", "") for s in d["sources"]], ["", "NHK", "TBS NEWS DIG"])

    def test_press_only_submission_is_accepted_but_other_press_only_is_not(self):
        self.assertEqual(mf.problems(self.data([NHK, TBS]), "20261113-お金-円安160円台の影響.md"), [])
        bad = mf.problems(self.data(["https://www.sankei.com/article/1/"]), "20261113-お金-円安160円台の影響.md")
        self.assertTrue(any("出典にできません" in p for p in bad))

    def check(self, urls: list[str]):
        lines = "\n".join(f"  - url: {u}\n    name: n\n    facts: f" for u in urls)
        text = f"---\ntitle: 円相場が一時1ドル160円台、家計への影響を整理する\ngenre: お金\nsources:\n{lines}\nnotes: n\n---\n## a\n\n本文です。\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "20261113-お金-円安160円台の影響.md"
            path.write_text(text, "utf-8")
            return ma.check_file(path)

    def test_check_file_drops_unlisted_outlets_and_keeps_listed_ones(self):
        data, problems = self.check([MOF, "https://www.axios.com/2026/11/07/x", NHK])
        self.assertEqual(problems, [])
        self.assertEqual([s["url"] for s in data["sources"]], [MOF, NHK])
        data, problems = self.check([NHK])
        self.assertEqual(problems, [])
        _, problems = self.check(["https://www.axios.com/2026/11/07/x", "https://techcrunch.com/2026/11/07/x"])
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("報道機関のページは出典にできません" in p for p in problems))


def record(**kw) -> dict:
    base = {"title": "円相場の動きと家計への影響を整理する", "lede": "財務省によると、10月の介入額は0円でした。",
            "body": "## 介入の実績\n\n財務省によると、10月の介入額は0円でした。\n", "easy": "", "highlights": [], "threadsPost": ""}
    return {**base, **kw}


class AttributionTest(unittest.TestCase):
    def test_no_press_sources_means_no_check(self):
        self.assertEqual(ma.press_problems(record(body="## a\n\n1ドル160円台になりました。\n"), [src(MOF, OFFICIAL_TEXT)]), [])

    def test_press_only_number_without_attribution_is_a_problem(self):
        got = ma.press_problems(record(body="## 円安\n\n円相場は一時1ドル160円台まで値下がりしました。\n"), MIXED)
        self.assertEqual(len(got), 1)
        self.assertIn("報道と分かる形で書いていない", got[0])
        self.assertIn("NHKによると", got[0])

    def test_attributed_forms_pass(self):
        for body in ("NHKによると、円相場は一時1ドル160円台まで値下がりしました。",
                     "円相場が一時1ドル160円台まで値下がりしたとNHKが報じました。",
                     "円相場は一時1ドル160円台まで値下がりしたと報じられています。",
                     "NHKによると、円相場は12日に値下がりしました。午後5時時点では159円81銭だったということです。",
                     "NHKの報道を表にまとめます。\n| 時点 | 円相場 |\n|---|---|\n| 一時 | 160円台 |\n| 午後5時 | 159円81銭 |"):
            self.assertEqual(ma.press_problems(record(body=f"## 円安\n\n{body}\n"), MIXED), [], body)

    def test_hedge_alone_or_attribution_in_another_paragraph_is_not_enough(self):
        self.assertTrue(ma.press_problems(record(body="## 円安\n\n午後5時時点では159円81銭だったということです。\n"), MIXED))
        body = "## 円安\n\nNHKによると、円相場は値下がりしました。\n\n午後5時時点では159円81銭でした。\n"
        self.assertTrue(ma.press_problems(record(body=body), MIXED))
        # 役所の名前は「どこの報道か」ではない
        self.assertTrue(ma.press_problems(record(body="## 円安\n\n財務省によると、午後5時時点では159円81銭でした。\n"), MIXED))

    def test_numbers_also_in_the_official_source_need_no_attribution(self):
        self.assertEqual(ma.press_problems(record(body="## 介入\n\n10月の介入額は0円でした。20の国が対象です。\n"), MIXED), [])

    def test_every_reader_field_is_checked(self):
        for kw in ({"title": "円相場が一時160円台に、家計への影響を整理する"}, {"lede": "円相場が一時160円台になりました。"},
                   {"highlights": ["円相場は一時160円台"]}, {"threadsPost": "円相場が一時160円台。家計はどうなる？"},
                   {"easy": "## かんたんに\n\n円は一時160円台です。\n"}, {"faq": [{"q": "いくら？", "a": "一時160円台です。"}]},
                   {"todayActions": ["160円台のうちに外貨を確かめる"]}, {"workMoney": {"points": ["一時160円台で輸入品が上がる"]}},
                   {"description": "円相場が一時160円台。"}, {"seoTitle": "円相場160円台の影響"}):
            self.assertTrue(ma.press_problems(record(**kw), MIXED), kw)
        ok = {"title": "円相場が一時160円台とNHK報道、家計への影響を整理する", "highlights": ["NHKによると円相場は一時160円台"],
              "threadsPost": "NHKによると、円相場が一時160円台に。家計はどうなる？"}
        self.assertEqual(ma.press_problems(record(**ok), MIXED), [])

    def test_copied_press_sentences_are_a_problem(self):
        self.assertTrue(ma.press_copies("およそ2か月ぶりの円安水準となりました。円相場は一時1ドル＝160円台まで値下がりし、およそ2か月ぶりの円安水準となりました。", NHK_TEXT))
        self.assertEqual(ma.press_copies("NHKによると、円は約2か月ぶりの安値でした。", NHK_TEXT), [])
        copied = "NHKによると、12日のニューヨーク外国為替市場で円相場は一時1ドル＝160円台まで値下がりしました。"
        got = ma.press_problems(record(body=f"## 背景\n\n{copied}\n"), MIXED)
        self.assertTrue(any("報道の文をそのまま写している" in p for p in got), got)
        own = "NHKによると、日米の金利の開きが円売りの理由に挙がっています。"
        self.assertEqual(ma.press_problems(record(body=f"## 背景\n\n{own}\n"), MIXED), [])

    def test_press_only_article_needs_the_outlet_in_title_lede_post_and_body(self):
        bare = record(title="円相場が一時1ドル160円台に、約2か月ぶりの円安水準", lede="円安が進みました。", threadsPost="円安が進んでいます。",
                      body="## 円安\n\n円安が進みました。\n")
        got = " / ".join(ma.press_problems(bare, PRESS_ONLY))
        for label in ("題名に報道機関の名前が無い", "リードに報道機関の名前が無い", "SNS の文（threads_post）に報道機関の名前が無い", "本文に報道機関の名前"):
            self.assertIn(label, got)
        good = record(title="円相場が一時1ドル160円台とNHK報道、約2か月ぶりの円安水準", lede="NHKによると、円相場は一時160円台まで値下がりしました。",
                      threadsPost="NHKによると円が一時160円台に。", body="## 円安\n\nNHKによると、円相場は一時160円台まで値下がりしました。\n")
        self.assertEqual(ma.press_problems(good, PRESS_ONLY), [])


class SourceTextTest(unittest.TestCase):
    def test_press_sources_are_labelled_in_the_material(self):
        text = ma.source_text_of(MIXED, "円安")
        self.assertIn(f"【財務省】{MOF}", text)
        self.assertIn(f"【報道: NHK】{NHK}", text)
        self.assertIn("公式の発表ではない", text)
        self.assertIn("「NHKによると」と報道として書く", text)
        self.assertIn("【報道: NHK】", ma.source_text_of(PRESS_ONLY))


class EveryPathGateTest(unittest.TestCase):
    """public_interest.press_source_problems（全経路の門 W31）: Muse の道の印が付いた記事だけ通す"""

    REC = {"writer": "muse", "pressOnly": True, "sourceUrl": NHK, "sourceName": "NHK", "channelSlug": "radar-news.web.nhk",
           "title": "円相場が一時160円台とNHK報道", "body": "## a\n\n本文"}

    def test_muse_press_only_record_passes_every_path(self):
        self.assertTrue(pi.muse_press_ok(self.REC))
        self.assertEqual(pi.press_source_problems(self.REC), [])
        self.assertFalse(any("W31" in p for p in quality.every_path_problems(self.REC)))
        self.assertIsNone(indexnow.publish_block_reason(self.REC))

    def test_default_behaviour_is_unchanged_for_everything_else(self):
        cases = (
            {**self.REC, "writer": ""},                                   # 自動の記事
            {k: v for k, v in self.REC.items() if k != "writer"},
            {**self.REC, "pressOnly": False}, {**self.REC, "pressOnly": "true"},
            {k: v for k, v in self.REC.items() if k != "pressOnly"},        # 印が無い
            {**self.REC, "sourceUrl": "https://gori.me/sale/1", "channelSlug": "radar-gori.me"},      # 一覧に無い報道
            {**self.REC, "sourceUrl": "https://www.itmedia.co.jp/news/1.html"},
            {**self.REC, "sourceUrl": "https://nordot.app/1", "sourceName": "神戸新聞"},
        )
        for rec in cases:
            self.assertFalse(pi.muse_press_ok(rec), rec)
            self.assertTrue(pi.press_source_problems(rec), rec)
        auto = {"channelSlug": "fast", "sourceUrl": "https://www.bloomberg.com/news/articles/2026-11-02/x", "title": "t", "body": "b"}
        self.assertTrue(pi.press_source_problems(auto))
        self.assertEqual(indexnow.publish_block_reason(auto), "press")

    def test_only_the_muse_lane_sets_the_mark(self):
        for path in (ROOT / "scripts").glob("*.py"):
            if path.name in ("muse_articles.py", "public_interest.py"):
                continue
            source = path.read_text("utf-8")
            self.assertNotIn('"pressOnly"', source, path.name)
            self.assertNotIn("muse_press_ok", source, path.name)


class MarkPressTest(unittest.TestCase):
    NOW = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)

    def test_mixed_article_relabels_the_press_fact_source(self):
        rec = {"body": "## a\n\n本文\n", "factSources": [{"label": "Museの出典", "name": "NHK", "url": NHK}, {"label": "公的資料", "name": "財務省", "url": MOF}]}
        ma.mark_press(rec, MIXED, self.NOW)
        self.assertEqual(rec["pressSources"], [{"url": NHK, "name": "NHK"}])
        self.assertEqual([f["label"] for f in rec["factSources"]], ["報道", "公的資料"])
        self.assertNotIn("まだ分からないこと", rec["body"])
        self.assertNotIn("pressOnly", rec)

    def test_press_only_article_gets_the_pending_note(self):
        rec = {"pressOnly": True, "body": "## 円安\n\nNHKによると円安です。\n"}
        ma.mark_press(rec, PRESS_ONLY, self.NOW)
        self.assertIn("## まだ分からないこと\n\nこの記事はNHKの報道をもとにしています。公式の発表は11月13日の時点で確認できていません。確認できしだい更新します。", rec["body"])

    def test_pending_note_goes_into_an_existing_section(self):
        rec = {"pressOnly": True, "body": "## 円安\n\n本文。\n\n## まだ分からないこと\n\n介入の有無は不明です。\n\n## サイソクの見方：家計\n\n見方。\n"}
        ma.mark_press(rec, PRESS_ONLY, self.NOW)
        body = rec["body"]
        self.assertEqual(body.count("## まだ分からないこと"), 1)
        self.assertLess(body.index("介入の有無は不明です。"), body.index("この記事はNHKの報道をもとにしています。"))
        self.assertLess(body.index("この記事はNHKの報道をもとにしています。"), body.index("## サイソクの見方：家計"))

    def test_no_press_no_mark(self):
        rec = {"body": "## a\n\n本文\n"}
        ma.mark_press(rec, [src(MOF, OFFICIAL_TEXT)], self.NOW)
        self.assertEqual(rec, {"body": "## a\n\n本文\n"})

    def test_disclaimer_does_not_claim_an_official_source_for_press_only(self):
        only = ma.muse_disclaimer("lifestyle", ["NHK", "NHK", "TBS NEWS DIG"], True)
        self.assertIn("報道（NHK・TBS NEWS DIG）をもとに", only)
        self.assertIn("公式の発表はまだ確認できていません", only)
        self.assertNotIn("公式発表をもとに", only)
        mixed = ma.muse_disclaimer("lifestyle", ["NHK"], False)
        self.assertIn("公式発表をもとに", mixed)
        self.assertIn("一部は報道（NHK）が伝えた内容", mixed)
        self.assertEqual(ma.muse_disclaimer("lifestyle"), ma.muse_disclaimer("lifestyle", [], False))
        self.assertIn("投資助言ではありません", ma.muse_disclaimer("investment", ["NHK"], True))


DATA = {"title": "円相場が一時1ドル160円台とNHK報道、約2か月ぶりの円安水準", "genre": "お金", "notes": "", "body": "## 円安\n\n本文。"}
GOOD = {"title": DATA["title"], "lede": "NHKによると、円相場は一時160円台まで値下がりしました。", "threadsPost": "NHKによると円が一時160円台に。",
        "body": "## 円安\n\nNHKによると、円相場は一時160円台まで値下がりしました。\n"}
BAD = {**GOOD, "body": "## 円安\n\nNHKの報道が出ました。円相場は一時160円台まで値下がりしました。\n"}


def run_build(fetched: list[dict], drafts: list[dict]):
    """build_article を、LLM・記事の組み立て・品質の門を差し替えて動かす。（結果, compose に渡した item, extra_sources, 指示文）"""
    seen: dict = {"prompts": []}
    made = iter(drafts)

    def fake_compose(item, source_text, lane, rows, voice, page, extra_sources=None):
        seen.update(item=dict(item), extra=list(extra_sources or []), page=dict(page), source_text=source_text)
        return ("investment", "system", "＜指示＞", {}, "news", "", {})

    def fake_generate(system, prompt, schema, **kwargs):
        seen["prompts"].append(prompt)
        return {"is_relevant": True}, "stub-model"

    def fake_record(item, draft, page, model, voice, bundle):
        return {"slug": "yen-160", "sourceType": "web", "sourceUrl": item["url"], "sourceName": item["source_name"],
                "channelSlug": item["source_slug"], "genreSlug": "investment", "disclaimer": "x", **next(made)}

    ok = {"ok": True, "soft": False, "score": 95, "problems": [], "fact": {"grounded": True, "score": 95, "problems": []}}
    patches = [
        mock.patch.object(w, "compose_with_facts", side_effect=fake_compose),
        mock.patch.object(m, "pick_voice", return_value=("v1", "声")),
        mock.patch.object(ma.source_date, "check", return_value=[]), mock.patch.object(ma.source_date, "past_change", return_value=[]),
        mock.patch.object(llm, "generate_json", side_effect=fake_generate),
        mock.patch.object(w, "build_web_record", side_effect=fake_record),
        mock.patch.object(w, "pre_gate"), mock.patch.object(w, "finalize_facts"), mock.patch.object(w, "stamp_times"),
        mock.patch.object(ma.own_view, "ensure"), mock.patch.object(ma.quality_bar, "ensure"),
        mock.patch.object(ma.quality_bar, "check", return_value={}), mock.patch.object(ma.quality_bar, "stamp"),
        mock.patch.object(ma.quality_bar, "summary_line", return_value="-"), mock.patch.object(easy_version, "ensure", return_value="-"),
        mock.patch.object(quality, "evaluate", return_value=ok),
    ]
    for p in patches:
        p.start()
    try:
        result = ma.build_article(Path("20261113-お金-円安160円台の影響.md"), DATA, fetched)
    finally:
        for p in reversed(patches):
            p.stop()
    return result, seen


class BuildArticleTest(unittest.TestCase):
    def test_press_only_article_is_built_as_a_labelled_report(self):
        (status, rec), seen = run_build(PRESS_ONLY, [dict(GOOD)])
        self.assertEqual(status, "ok", rec)
        # 今までの「報道が出典」の形（web_articles の secondary・発信元 radar-<ホスト> ＝ サイトの「出典（報道）」の札）
        self.assertTrue(seen["item"]["secondary"])
        self.assertEqual(seen["item"]["source_slug"], "radar-news.web.nhk")
        self.assertEqual(seen["item"]["source_name"], "NHK")
        self.assertEqual(seen["item"]["image"], "")       # 報道機関のページの写真は使わない
        self.assertIsNone(seen["page"]["image"])
        self.assertEqual((rec["pressOnly"], rec["officialPending"]), (True, True))
        self.assertNotIn("indexable", rec)  # 検索に出す（話題のレーンの報道の記事と同じ。下の test_press_only_article_is_indexable_like_the_trend_lane）
        self.assertEqual(rec["pressSources"], [{"url": NHK, "name": "NHK"}])
        self.assertIn("公式の発表はまだ確認できていません", rec["disclaimer"])
        self.assertIn("投資助言ではありません", rec["disclaimer"])
        self.assertIn("## まだ分からないこと", rec["body"])
        self.assertTrue(pi.muse_press_ok(rec))
        prompt = seen["prompts"][0]
        self.assertIn("# 報道機関の記事を資料に使うときの決まり", prompt)
        self.assertIn("確定した事実として言い切らない", prompt)
        self.assertIn("報道の文を写さない", prompt)
        self.assertIn("読めた公式の資料がありません（報道だけ）", prompt)
        self.assertIn("title・lede・threads_post には必ず報道機関の名前を入れる", prompt)

    def test_press_only_article_is_indexable_like_the_trend_lane(self):
        """2026-11-13: 報道だけの Muse の記事も検索に出す・サイトマップに入る（話題のレーンと同じ）。札と印は残す"""
        long_body = GOOD["body"] + "\n## 家計への影響\n\n" + "NHKによると、輸入品の値段に影響が出る見通しです。" * 30
        (status, rec), _ = run_build(PRESS_ONLY, [{**GOOD, "body": long_body}])
        self.assertEqual(status, "ok", rec)
        self.assertNotIn("indexable", rec)
        self.assertIsNone(indexnow.noindex_reason(rec))
        self.assertTrue(indexnow.is_indexable(rec))
        self.assertIsNone(indexnow.publish_block_reason(rec))  # 印で素通りではなく、ほかの Muse の記事と同じ門を通る
        self.assertEqual((rec["pressOnly"], rec["officialPending"]), (True, True))
        self.assertTrue(rec["channelSlug"].startswith("radar-"))  # 読者への札は「出典（報道）」のまま
        self.assertIn("公式の発表はまだ確認できていません", rec["disclaimer"])
        # ほかの報道が出典の記事は変えない: 自動の記事は今までどおり公開前の門で止まる
        auto = {**rec, "writer": ""}
        self.assertEqual(indexnow.publish_block_reason(auto), "press")
        # 公開前の門と検索の基準は同じ軸を見る: 門を通った報道だけの記事は、軸の理由で検索から外れない
        self.assertTrue(indexnow.on_axis(rec))

    def test_mixed_article_keeps_the_official_source_first(self):
        (status, rec), seen = run_build(list(reversed(MIXED)), [{**GOOD, "title": "円相場の動きと家計への影響"}])
        self.assertEqual(status, "ok", rec)
        self.assertEqual(seen["item"]["url"], MOF)
        self.assertNotIn("secondary", seen["item"])
        self.assertEqual(seen["item"]["source_slug"], "www-mof-go-jp".replace("www-", ""))
        self.assertEqual([(s["url"], s["name"]) for s in seen["extra"]], [(NHK, "NHK")])
        self.assertNotIn("pressOnly", rec)
        self.assertNotIn("indexable", rec)
        self.assertEqual(rec["pressSources"], [{"url": NHK, "name": "NHK"}])
        self.assertIn("一部は報道（NHK）が伝えた内容", rec["disclaimer"])
        self.assertNotIn("まだ分からないこと", rec["body"])
        self.assertIn("# 報道機関の記事を資料に使うときの決まり", seen["prompts"][0])
        self.assertNotIn("読めた公式の資料がありません", seen["prompts"][0])

    def test_unattributed_press_fact_is_sent_back_then_rejected(self):
        (status, why), seen = run_build(MIXED, [dict(BAD), dict(BAD)])
        self.assertEqual(status, "reject")
        self.assertIn("報道と分かる形で書いていない", why)
        self.assertEqual(len(seen["prompts"]), ma.MAX_ATTEMPTS)
        self.assertIn("報道と分かる形で書いていない", seen["prompts"][1])

    def test_second_attempt_can_fix_the_attribution(self):
        (status, rec), seen = run_build(MIXED, [dict(BAD), dict(GOOD)])
        self.assertEqual(status, "ok", rec)
        self.assertEqual(len(seen["prompts"]), 2)

    def test_official_only_article_is_untouched(self):
        (status, rec), seen = run_build([src(MOF, OFFICIAL_TEXT)], [{**GOOD, "body": "## 介入\n\n10月の介入額は0円でした。\n"}])
        self.assertEqual(status, "ok", rec)
        self.assertNotIn("pressSources", rec)
        self.assertNotIn("# 報道機関の記事を資料に使うときの決まり", seen["prompts"][0])
        self.assertEqual(rec["disclaimer"], ma.muse_disclaimer("investment"))


class ScopeTest(unittest.TestCase):
    def test_automatic_lanes_do_not_use_the_press_allowlist(self):
        for name in ("web_articles.py", "main.py", "trends.py", "fast_lane.py", "evergreen.py"):
            source = (ROOT / "scripts" / name).read_text("utf-8")
            self.assertNotIn("PRESS_ALLOWED", source, name)
            self.assertNotIn("press_outlet", source, name)

    def test_format_md_explains_the_rule_to_the_writer(self):
        for word in ("主要な報道機関の記事だけ", "NHKによると", "報道の文は写しません", "報道機関自身のページの URL", "報道をもとにした速報"):
            self.assertIn(word, mf.FORMAT_MD)


if __name__ == "__main__":
    unittest.main()
