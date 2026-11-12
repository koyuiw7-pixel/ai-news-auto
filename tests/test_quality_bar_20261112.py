"""記事の8つの基準（2026-11-12 オーナー「量を超えることができるレベルの最高の記事」。scripts/quality_bar.py）

保留の決まりを決めたときの測定（2026-11-12・直近7日の暮らしとお金の記事 311本。公開の前の点検 at_publish）:
  8つ全部を満たした記事: 0本（4「サイソクの見方」は11/12に始めたので94%に無い。7 関連リンク2本以上も94%に無い）
  足りない点の多い順: 4 サイソクの見方 94%・7 内部リンク 94%・6 分かりやすさ 48%・3 自分の場合 39%・1 最初の3行 27%・8 決まり文句 2%・5 すること 5%
  手直しの前に 1・3・5 のどれかが足りない記事: 168本（54%）
  無料モデルでの手直しの試し（6本・統計と倒産件数と新商品の記事）: 1・3・5 が足りないまま 4本 → 保留
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quality_bar as qb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def setUpModule():
    # 関連記事の候補は空にする（content/articles の中身で結果が変わらないように）。候補の選び方は PageRelatedTest で確かめる
    qb._CORPUS = qb.corpus([])  # noqa: SLF001


def tearDownModule():
    qb._CORPUS = None  # noqa: SLF001

GOOD_LEDE = ("年金を受け取っている人は、12月15日の振込から月400円増えます。対象は老齢年金生活者支援給付金を受け取っている約600万人です。"
             "手続きは不要で、日本年金機構から通知が届きます。")
GOOD_BODY = """年金を受け取っている人は、12月15日の振込から給付金が月400円増えます（日本年金機構「年金生活者支援給付金」、11/12確認）。

## 増えるのは月400円、年4,800円

| 受け取っている人 | 今の月額 | 12月からの月額 |
|---|---|---|
| 老齢の給付金 | 5,450円 | 5,850円 |

月400円×12か月＝4,800円です（サイソク編集部の計算）。

## 手続きは不要、通知はがきで確かめる

手続きは不要です。日本年金機構から届く通知で、12月15日の振込額を確かめてください。分からないときは、ねんきんダイヤル（0570-05-1165）に電話します。
関連の記事: [年金の12月の支給日](/articles/nenkin-december) と [給付金の受け取り方](/articles/kyufukin-guide)。

## サイソクの見方：振込が増えるなら、12月の通帳で確かめる

月400円は前回の改定より大きく、年金だけで暮らす人ほど助かるとみられます。振込額が5,850円に増えていなければ、ねんきんダイヤルで確かめるのが目安です。
年金のほかに収入がある人は、給付金の対象かどうかを通知で確かめてください。
"""
# 3（自分の場合）だけが足りない本文（表・計算・「〜の人は〜」が無い）
NO_CASE_BODY = """年金を受け取っている人は、12月15日の振込から給付金が月400円増えます（日本年金機構「年金生活者支援給付金」、11/12確認）。

## 手続きは不要、通知はがきで確かめる

手続きは不要です。日本年金機構から届く通知で、12月15日の振込額を確かめてください。問い合わせ先は、ねんきんダイヤル（0570-05-1165）です。
関連の記事: [年金の12月の支給日](/articles/nenkin-december) と [給付金の受け取り方](/articles/kyufukin-guide)。

## サイソクの見方：振込が増えるなら、12月の通帳で確かめる

月400円は前回の改定より大きく、年金だけで暮らす世帯ほど助かるとみられます。12月の振込額は、通帳や通知で確かめられます。
"""
THIN_LEDE = "国土交通省は11日、9月の建設工事受注動態統計を公表しました。"
THIN_BODY = """国土交通省は11日、9月の建設工事受注動態統計を公表しました。受注高は12兆1,013億円でした。

## 9月の受注高

元請受注高は8兆824億円、下請受注高は4兆189億円です。今後の動向が注目されます。
"""
SOURCE = ("年金生活者支援給付金は12月15日の振込から月額5,850円になります。前の月額は5,450円で、400円の引き上げです。"
          "対象は約600万人。手続きは不要です。問い合わせはねんきんダイヤル 0570-05-1165。")


def rec(**kw) -> dict:
    base = {"slug": "kyufukin-400", "title": "年金生活者支援給付金、12月から月400円増える", "genreSlug": "public", "newsType": "policy",
            "lede": GOOD_LEDE, "body": GOOD_BODY, "sourceUrl": "https://www.nenkin.go.jp/a", "sourceName": "日本年金機構",
            "todayActions": ["日本年金機構の通知はがきで、12月15日の振込額を確かめる"], "publishedAt": "2026-11-12T03:00:00+00:00"}
    base.update(kw)
    return base


class FakeLLM:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, system, prompt, schema, **kw):
        self.calls.append((system, prompt, kw))
        return self.answers.pop(0), "fake-model"


class CheckTest(unittest.TestCase):
    def test_good_article_meets_all_eight(self):
        r = qb.check(rec(), at_publish=True)
        self.assertEqual(r["missing"], [], r["notes"])
        self.assertEqual(r["score"], 8)

    def test_thin_statistics_article_misses_the_reader_points(self):
        r = qb.check(rec(slug="construction", title="9月の建設工事受注は12兆1,013億円", genreSlug="business", lede=THIN_LEDE,
                         body=THIN_BODY, todayActions=[]), at_publish=True)
        for p in (1, 3, 4, 5, 7, 8):
            self.assertIn(p, r["missing"], r["notes"])
        self.assertIn("だれに", r["notes"][1])
        self.assertIn("決まり文句", r["notes"][8])

    def test_point1_reads_lede_and_first_paragraph(self):
        self.assertIsNone(qb.p1_lead(rec()))
        self.assertIn("どのくらい", qb.p1_lead(rec(lede="会社員の人は、来年1月から申告の方法が変わります。", body="制度の説明です。")) or "どのくらい")
        # 数字で言えない発表でも、だれに・いつと、読者に何を意味するか（必要・不要）があればよい
        self.assertIsNone(qb.p1_lead(rec(lede="マイナ保険証を使っている人は、12月2日から紙の保険証が使えなくなります。", body="説明。")))

    def test_point3_accepts_table_calc_or_two_case_lines(self):
        self.assertIsNone(qb.p3_case(rec()))
        lines = "年金だけで暮らす人は、振込額を確かめます。\n\n働いて収入がある人は、対象かどうかを通知で確かめます。"
        self.assertIsNone(qb.p3_case(rec(body=lines)))
        self.assertIsNotNone(qb.p3_case(rec(body="給付金が増えます。対象は約600万人です。")))
        # 公開のあとで足す判断ガイド（depth_fields）は、公開の前の点検では数えない
        guided = rec(body="給付金が増えます。", decisionGuide=[{"question": "q"}])
        self.assertIsNone(qb.p3_case(guided))
        self.assertIsNotNone(qb.p3_case(guided, body_only=True))

    def test_point5_needs_where_or_deadline_or_explicit_no_procedure(self):
        self.assertIsNone(qb.p5_actions(rec(body="手続きは不要です。自動で支給されます。", todayActions=[])))
        self.assertIsNotNone(qb.p5_actions(rec(body="給付金が増えます。", todayActions=[])))
        vague = qb.p5_actions(rec(body="内容を確認しましょう。", todayActions=[]))
        self.assertIn("どこで", vague)
        self.assertIsNone(qb.p5_actions(rec(body="申請は市区町村の窓口で12月25日までに行います。", todayActions=[])))

    def test_point5_and_3_do_not_apply_to_announcements_without_reader_action(self):
        r = rec(title="財務大臣が米財務長官と会談", body="会談しました。", todayActions=[])
        self.assertIsNone(qb.p3_case(r))
        self.assertIsNone(qb.p5_actions(r))

    def test_point6_acronyms_and_numbers_without_table(self):
        self.assertIn("略語", qb.p6_clear(rec(body="新しいCVSSの点数は9.8です。")))
        self.assertIsNone(qb.p6_clear(rec(body="CVSS（深刻さを示す点数）は9.8です。")))
        self.assertIsNone(qb.p6_clear(rec(body="地方公共団体情報システム機構（J-LIS）から届きます。")))
        many = "。".join(f"{i}月は{i * 100}円" for i in range(1, 12)) + "。"
        self.assertIn("表も図も無い", qb.p6_clear(rec(body=many)))
        self.assertIsNone(qb.p6_clear(rec(body=many + "\n\n| 月 | 円 |\n|---|---|\n| 1 | 100 |\n")))

    def test_point7_counts_body_links_related_and_date_pages(self):
        self.assertEqual(len(qb.internal_links(rec())), 2)
        self.assertIsNotNone(qb.p7_links(rec(body="リンクなし", relatedSlugs=["a"])))
        self.assertIsNone(qb.p7_links(rec(body="リンクなし", relatedSlugs=["a", "b"])))
        self.assertIsNone(qb.p7_links(rec(body="[ツール](/tools/furusato-limit)", relatedSlugs=["a"])))
        # 記事ページが案内する日程ページ（content/money-dates.json の式）も数える
        dated = rec(title="個人向け国債の11月募集", body="本文", relatedSlugs=["a"], tags=[])
        self.assertIn("/dates/kojin-muke-kokusai", qb.internal_links(dated))
        self.assertNotIn("/articles/kyufukin-400", qb.internal_links(rec(relatedSlugs=["kyufukin-400"])))

    def test_point8_boilerplate_only_without_facts(self):
        self.assertIn("決まり文句", qb.p8_natural(rec(body="今後の動向が注目されます。")))
        self.assertIsNone(qb.p8_natural(rec(body="12月の利率が0.2ポイント上がると注目されます。")))
        self.assertIn("型の見出し", qb.p8_natural(rec(body="## まとめ\n\n給付金は12月から増えます。")))
        self.assertIn("くり返し", qb.p8_natural(rec(body="給付金は12月15日の振込から月400円増えることが決まりました。\n\n給付金は12月15日の振込から月400円増えることが決まりました。")))
        self.assertIn("使わない文字", qb.p8_natural(rec(title="給付金｜12月から")))

    def test_point2_uses_the_fact_gate_result(self):
        self.assertIsNone(qb.p2_sources(rec(), {"ok": True}))
        self.assertIsNotNone(qb.p2_sources(rec(), {"ok": False}))
        self.assertIsNotNone(qb.p2_sources(rec(sourceUrl="", sourceName="")))
        self.assertIsNotNone(qb.p2_sources(rec(qualityScore=60)))

    def test_point4_reuses_own_view(self):
        self.assertIsNone(qb.p4_view(rec()))
        self.assertIn("サイソクの見方", qb.p4_view(rec(body="給付金が増えます。")))

    def test_stamp_records_missing_points_on_the_article(self):
        r = rec(body="給付金が増えます。")
        bar = qb.stamp(r, qb.check(r, at_publish=True))
        self.assertIs(r["qualityBar"], bar)
        self.assertIn(3, bar["missing"])
        self.assertIn("3", bar["notes"])
        self.assertIn("checkedAt", bar)


class PageRelatedTest(unittest.TestCase):
    def test_page_related_counts_articles_on_the_same_topic(self):
        pool = qb.corpus([
            {"slug": "x1", "title": "年金生活者支援給付金の請求のしかた", "tags": ["年金生活者支援給付金", "ねんきんダイヤル"], "genreSlug": "public"},
            {"slug": "x2", "title": "年金の振込日", "tags": ["年金生活者支援給付金"], "genreSlug": "public"},
            {"slug": "x3", "title": "新しいスマホ", "tags": ["スマホ"], "genreSlug": "tech-gadget"},
            {"slug": "x4", "title": "同じ発表", "tags": ["年金生活者支援給付金", "ねんきんダイヤル"], "genreSlug": "public", "sourceUrl": "https://www.nenkin.go.jp/a"},
        ])
        r = rec(tags=["年金生活者支援給付金", "ねんきんダイヤル"], body="本文")
        self.assertEqual(qb.page_related(r, pool), ["x1", "x2"])  # 同じ出典の記事（x4）と関係の無い記事（x3）は数えない
        self.assertIsNone(qb.p7_links(r, pool))
        self.assertIsNotNone(qb.p7_links(r, False))


class RepairTest(unittest.TestCase):
    def missing_case(self) -> dict:
        r = rec(body=NO_CASE_BODY)
        self.assertEqual(qb.check(r, at_publish=True)["missing"], [3])
        return r

    @staticmethod
    def patch(**kw) -> dict:
        return {"lede": "", "first_paragraph": "", "insert_markdown": "", "replacements": [], **kw}

    TABLE = ("## 老齢の給付金は、12月から月5,850円\n\n| 受け取っている人 | 今の月額 | 12月からの月額 |\n|---|---|---|\n"
             "| 老齢の給付金 | 5,450円 | 5,850円 |\n\n月400円×12か月＝4,800円です（サイソク編集部の計算）。")

    def test_repair_adds_missing_point_with_source_facts_and_keeps_other_text(self):
        r = self.missing_case()
        fake = FakeLLM(self.patch(insert_markdown=self.TABLE))
        result = qb.ensure(r, SOURCE, log=lambda *_: None, generate=fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertNotIn(3, result["missing"])
        self.assertTrue(r["qualityBar"]["repaired"])
        self.assertEqual(r["qualityBar"]["before"], [3])
        # 足した章は「サイソクの見方」の前。ほかの文は1字も変わらない
        self.assertLess(r["body"].index("| 老齢の給付金"), r["body"].index("## サイソクの見方"))
        self.assertEqual(r["body"].replace(self.TABLE + "\n\n", ""), NO_CASE_BODY)
        prompt = fake.calls[0][1]
        self.assertIn("自分の場合", prompt)
        self.assertIn(SOURCE[:30], prompt)
        self.assertEqual(fake.calls[0][2]["purpose"], "helper")

    def test_patch_replacements_and_first_paragraph(self):
        body, lede, skipped = qb.apply_patch("最初の段落です。\n\n## 章\n\n今後の動向が注目されます。\n", "前のリード。", self.patch(
            lede="新しいリード。", first_paragraph="新しい最初の段落です。",
            replacements=[{"before": "今後の動向が注目されます。", "after": ""}, {"before": "本文に無い文。", "after": "x"}]))
        self.assertEqual(lede, "新しいリード。")
        self.assertTrue(body.startswith("新しい最初の段落です。"))
        self.assertNotIn("注目されます", body)
        self.assertEqual(len(skipped), 1)

    def test_repair_with_numbers_not_in_the_source_is_not_used(self):
        r = self.missing_case()
        invented = "## 障害の給付金は月7,300円\n\n| 人 | 月額 |\n|---|---|\n| 障害の給付金 | 7,300円 |"
        qb.ensure(r, SOURCE, log=lambda *_: None, generate=FakeLLM(self.patch(insert_markdown=invented)))
        self.assertEqual(r["body"], NO_CASE_BODY)
        self.assertFalse(r["qualityBar"]["repaired"])

    def test_wrong_calculation_is_not_used_but_a_correct_one_is(self):
        ok, bad = qb.calc_results("月400円×12か月＝4,800円（サイソク編集部の計算）")
        self.assertEqual((ok, bad), ({"4,800"}, []))
        ok, bad = qb.calc_results("月400円×12か月＝5,800円（サイソク編集部の計算）")
        self.assertTrue(bad)
        r = self.missing_case()
        wrong = "## 年金だけの人は年5,800円増える\n\n年金だけの人は、月400円×12か月＝5,800円です（サイソク編集部の計算）。\n\n収入がある人は、通知で確かめます。"
        qb.ensure(r, SOURCE + "5,800", log=lambda *_: None, generate=FakeLLM(self.patch(insert_markdown=wrong)))
        self.assertEqual(r["body"], NO_CASE_BODY)

    def test_repair_that_touches_the_view_or_does_not_improve_is_not_used(self):
        r = self.missing_case()
        view_sentence = "12月の振込額は、通帳や通知で確かめられます。"
        body, _, skipped = qb.apply_patch(NO_CASE_BODY, "", self.patch(replacements=[{"before": view_sentence, "after": "年金だけの人は助かります。"}]))
        self.assertEqual(body, NO_CASE_BODY)
        self.assertTrue(skipped)
        qb.ensure(r, SOURCE, log=lambda *_: None, generate=FakeLLM(self.patch(insert_markdown="## 給付金が増える\n\n給付金が増えます。")))
        self.assertEqual(r["body"], NO_CASE_BODY)
        self.assertFalse(r["qualityBar"]["repaired"])

    def test_breaking_alert_is_not_slowed_and_marked_for_later_repair(self):
        r = rec(body="給付金が増えます。", breaking=True, todayActions=[])
        fake = FakeLLM()
        result = qb.ensure(r, SOURCE, log=lambda *_: None, generate=fake)
        self.assertEqual(fake.calls, [])
        self.assertIn(3, result["missing"])
        self.assertTrue(r["qualityBar"]["repairLater"])
        self.assertIsNone(qb.hold_reason(r))
        # 速報レーン・大きなニュース（urgent）も同じ
        r2 = rec(body="給付金が増えます。", todayActions=[])
        qb.ensure(r2, SOURCE, urgent=True, log=lambda *_: None, generate=fake)
        self.assertEqual(fake.calls, [])
        self.assertIsNone(qb.hold_reason(r2, urgent=True))
        self.assertTrue(r2["qualityBar"]["repairLater"])

    def test_link_fill_adds_related_articles_without_llm(self):
        r = rec(body=GOOD_BODY.replace("関連の記事: [年金の12月の支給日](/articles/nenkin-december) と [給付金の受け取り方](/articles/kyufukin-guide)。", ""))
        self.assertIn(7, qb.check(r, at_publish=True)["missing"])
        fake = FakeLLM()
        result = qb.ensure(r, SOURCE, related=[{"slug": "kyufukin-400"}, {"slug": "nenkin-a"}, {"slug": "nenkin-b"}], log=lambda *_: None,
                           generate=fake)
        self.assertEqual(fake.calls, [])  # 7 だけが足りないなら LLM を使わない
        self.assertEqual(r["relatedSlugs"][:2], ["nenkin-a", "nenkin-b"])
        self.assertNotIn("kyufukin-400", r["relatedSlugs"])
        self.assertNotIn(7, result["missing"])

    def test_llm_failure_does_not_stop_the_pipeline(self):
        def boom(*a, **k):
            raise RuntimeError("quota")

        r = rec(body="給付金が増えます。", todayActions=[])
        notes = []
        qb.ensure(r, SOURCE, log=notes.append, generate=boom)
        self.assertTrue(any("失敗" in n for n in notes))
        self.assertIsNotNone(qb.hold_reason(r))


class HoldTest(unittest.TestCase):
    def test_life_article_missing_1_3_or_5_is_held(self):
        no_action = NO_CASE_BODY.replace("手続きは不要です。日本年金機構から届く通知で、12月15日の振込額を確かめてください。問い合わせ先は、ねんきんダイヤル（0570-05-1165）です。",
                                         "給付金の額は物価に合わせて決まります。").replace("## 手続きは不要、通知はがきで確かめる", "## 額は物価に合わせて決まる")
        no_action = no_action.replace("12月の振込額は、通帳や通知で確かめられます。", "12月の振込額は、通帳に記帳されるのを待つのが目安です。")
        cases = {
            3: rec(body=NO_CASE_BODY),
            5: rec(body=no_action + "\n| 人 | 月額 |\n|---|---|\n| 老齢 | 5,850円 |\n", todayActions=[]),
            1: rec(lede="日本年金機構が発表しました。", body="発表がありました。\n\n" + GOOD_BODY.split("\n\n", 1)[1]),
        }
        for point, r in cases.items():
            result = qb.check(r, at_publish=True)
            self.assertIn(point, result["missing"], (point, result))
            reason = qb.hold_reason(r)
            self.assertIsNotNone(reason, (point, result))
            self.assertIn("記事の基準に足りない", reason)
            self.assertIn(f"{point}.", reason)

    def test_good_article_is_not_held(self):
        self.assertIsNone(qb.hold_reason(rec()))

    def test_missing_only_soft_points_is_not_held(self):
        r = rec(body=GOOD_BODY + "\n\n今後の動向が注目されます。\n", relatedSlugs=[])
        r["body"] = r["body"].replace("[年金の12月の支給日](/articles/nenkin-december) と [給付金の受け取り方](/articles/kyufukin-guide)", "")
        missing = qb.check(r, at_publish=True)["missing"]
        self.assertTrue({7, 8} <= set(missing))
        self.assertIsNone(qb.hold_reason(r))
        self.assertEqual(r["qualityBar"]["missing"], missing)

    def test_exemptions_breaking_disaster_other_genres_and_no_reader_action(self):
        thin = {"body": "給付金が増えます。", "lede": "給付金について。", "todayActions": []}
        self.assertIsNone(qb.hold_reason(rec(**thin, breaking=True)))
        self.assertIsNone(qb.hold_reason(rec(**thin, newsType="breaking")))
        self.assertIsNone(qb.hold_reason(rec(**thin, disaster=True)))
        self.assertIsNone(qb.hold_reason(rec(**thin, fastLane=True)))
        self.assertIsNone(qb.hold_reason(rec(**thin, slug="quake-20261112")))
        self.assertIsNone(qb.hold_reason(rec(**thin, genreSlug="ai")))
        self.assertIsNone(qb.hold_reason(rec(**thin, title="財務大臣が米財務長官と会談")))
        self.assertIsNotNone(qb.hold_reason(rec(**thin)))

    def test_fact_gate_failure_is_never_relaxed(self):
        # 基準を満たしても、事実確認に落ちた記事の点 2 は満たさない（この門は保留を決める前に、今までどおり落とす）
        self.assertIn(2, qb.check(rec(), {"ok": False, "soft": False})["missing"])


class WiringTest(unittest.TestCase):
    def test_every_path_runs_the_checker(self):
        web = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("quality_bar.ensure(record, source_text, context, urgent=view_urgent(item), log=log)", web)
        self.assertIn("quality_bar.hold_reason(record, urgent=view_urgent(item), verdict=verdict)", web)
        # 手直しは事実確認（quality.evaluate）の前、保留は事実確認に合格したあと（finish の中）
        self.assertLess(web.index("quality_bar.ensure(record"), web.index("verdict = quality.evaluate(record, source_text, kind, context, check_facts=not args.no_gate)\n                tag"))
        deep = (ROOT / "scripts" / "deep_dive.py").read_text("utf-8")
        self.assertIn("w.quality_bar.ensure(record", deep)
        self.assertIn("w.quality_bar.hold_reason(record", deep)
        angle = (ROOT / "scripts" / "angle_articles.py").read_text("utf-8")
        self.assertIn("w.quality_bar.ensure(record", angle)
        self.assertIn("w.quality_bar.hold_reason(record", angle)
        muse = (ROOT / "scripts" / "muse_articles.py").read_text("utf-8")
        self.assertIn("quality_bar.ensure(record, source_text, context, log=log)", muse)
        self.assertNotIn("quality_bar.hold_reason", muse)  # Muse の記事は「落とす理由は嘘だけ」（記録だけ）
        main = (ROOT / "scripts" / "main.py").read_text("utf-8")
        self.assertIn("quality_bar.hold_reason(record)", main)
        self.assertIn("quality_bar.stamp(record, bar)", main)
        thicken = (ROOT / "scripts" / "thicken_short.py").read_text("utf-8")
        self.assertIn("quality_bar.stamp(new, bar", thicken)
        workflow = (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8")
        self.assertIn("scripts/quality_bar.py --repair-later", workflow)

    def test_prompts_carry_the_rule_and_no_forbidden_words(self):
        import web_articles as w  # noqa: PLC0415

        item = {"source_name": "日本年金機構", "title": "給付金", "published_at": datetime.now(timezone.utc), "url": "https://www.nenkin.go.jp/a"}
        self.assertIn(qb.PROMPT_RULE, w.build_prompt(item, "本文"))
        self.assertIn(qb.PROMPT_RULE, w.build_broad_prompt(item, "本文", w.GENRES_BY_SLUG["public"]))
        self.assertIn(qb.PROMPT_RULE, w.build_trend_prompt({"title": "給付金", "summary": ""}, [{"url": "https://example.com", "text": "t"}],
                                                           w.GENRES_BY_SLUG["public"]))
        self.assertIn("quality_bar.prompt_block()", (ROOT / "scripts" / "main.py").read_text("utf-8"))
        for text in (qb.PROMPT_RULE, qb.REPAIR_PROMPT, qb.REPAIR_SYSTEM, *qb.POINT_HOWTO.values()):
            self.assertNotIn("｜", text)
            self.assertNotIn("ざっくり", text)

    def test_muse_guidance_lists_the_eight_points(self):
        import muse_format  # noqa: PLC0415

        section = muse_format.FORMAT_MD.split("## 記事の8つの基準", 1)[1].split("## 見本", 1)[0]
        for word in ("最初の3行", "確認日", "（サイソク編集部の計算）", "〜の人は〜", "サイソクの見方", "手続きは不要", "（ ）で言い換える",
                     "/dates", "/tools", "/compare", "/guides", "注目されます", "水増し", "落とす理由は嘘だけ"):
            self.assertIn(word, section)
        self.assertNotIn("｜", section)
        self.assertNotIn("ざっくり", section)


class ReportTest(unittest.TestCase):
    def articles(self) -> list[dict]:
        out = []
        for i in range(8):
            r = rec(slug=f"a{i}", title=f"給付金の記事{i}", publishedAt=f"2026-11-12T0{i}:10:00+00:00")
            if i % 2:
                r["body"] = "給付金が増えます。"
            out.append(r)
        out.append(rec(slug="old", publishedAt="2026-11-10T01:00:00+00:00"))
        return out

    def test_daily_report_samples_five_articles_with_the_eight_points(self):
        text = qb.daily_report(self.articles(), "2026-11-12")
        self.assertIn("この日に公開した記事 8 本から 5 本", text)
        self.assertEqual(text.count("| 1 | 最初の3行"), 5)
        self.assertNotIn("/articles/old", text)
        self.assertIn("8つ全部を満たした記事 4/8 本", text)
        self.assertEqual(text, qb.daily_report(self.articles(), "2026-11-12"))  # 同じ日なら同じ5本（会議で見直せる）
        self.assertNotIn("｜", text)

    def test_daily_report_writes_to_the_meeting_folder(self):
        self.assertEqual(qb.DAILY_DIR, ROOT / "out" / "strategy_20261110" / "quality_daily")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(qb, "load_articles", return_value=self.articles()), \
                mock.patch.object(sys, "argv", ["quality_bar.py", "--daily", "2026-11-12", "--out", f"{tmp}/2026-11-12.md"]), \
                mock.patch("builtins.print"):
            qb.main()
            self.assertIn("記事の8つの基準の抜き取り（2026-11-12）", Path(f"{tmp}/2026-11-12.md").read_text("utf-8"))

    def test_measure_counts_distribution_and_holds(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        m = qb.measure(self.articles(), now, days=7, at_publish=True)
        self.assertEqual(m["articles"], 9)
        self.assertEqual(m["all8"], 5)
        self.assertEqual(m["hold"], 4)
        self.assertEqual(m["perDay"]["2026-11-12"], [8, 4])


class RepairLaterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        self.article = rec(slug="breaking-a", body=NO_CASE_BODY, breaking=True,
                           publishedAt=(self.now - timedelta(hours=2)).isoformat(),
                           qualityBar={"missing": [3], "repairLater": True})
        (self.dir / "breaking-a.json").write_text(json.dumps(self.article, ensure_ascii=False), "utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_later(self, verdict: dict, body: str):
        import feeds  # noqa: PLC0415
        import llm  # noqa: PLC0415
        import quality  # noqa: PLC0415

        fake = FakeLLM({"lede": "", "first_paragraph": "", "insert_markdown": body, "replacements": []})
        with mock.patch.object(qb, "ARTICLES_DIR", self.dir), mock.patch.object(feeds, "fetch_article_text", return_value={"text": SOURCE * 10}), \
                mock.patch.object(llm, "generate_json", fake), mock.patch.object(quality, "evaluate", return_value=verdict):
            return qb.repair_later([json.loads(json.dumps(self.article))], self.now, apply=True, log=lambda *_: None), fake

    def test_repaired_breaking_article_is_saved_only_after_the_fact_gate(self):
        rows, fake = self.run_later({"ok": True, "score": 90}, RepairTest.TABLE)
        self.assertEqual(len(fake.calls), 1)
        saved = json.loads((self.dir / "breaking-a.json").read_text("utf-8"))
        self.assertIn("| 老齢の給付金 | 5,450円 | 5,850円 |", saved["body"])
        self.assertTrue(saved["breaking"])  # 速報の印は元のまま
        self.assertEqual(saved["qualityBar"]["missing"], [])
        self.assertIn("repairedLaterAt", saved["qualityBar"])
        self.assertEqual(rows[0]["after"], [])

    def test_repair_that_fails_the_fact_gate_is_not_saved(self):
        rows, _ = self.run_later({"ok": False, "soft": False, "problems": ["創作"]}, RepairTest.TABLE)
        saved = json.loads((self.dir / "breaking-a.json").read_text("utf-8"))
        self.assertEqual(saved["body"], NO_CASE_BODY)
        self.assertIn("laterTriedAt", saved["qualityBar"])  # 1本につき1回だけ試す
        self.assertIn("事実確認に合格しなかった", rows[0]["why"])

    def test_fresh_or_already_tried_articles_are_skipped(self):
        fresh = {**self.article, "publishedAt": (self.now - timedelta(minutes=5)).isoformat()}
        tried = {**self.article, "slug": "b", "qualityBar": {"repairLater": True, "laterTriedAt": "x"}}
        self.assertEqual(qb.repair_later([fresh, tried], self.now, apply=False, log=lambda *_: None), [])


if __name__ == "__main__":
    unittest.main()
