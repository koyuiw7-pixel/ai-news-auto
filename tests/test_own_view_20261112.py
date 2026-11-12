"""「サイソクの見方」の章と中身の下限（2026-11-12 オーナー「ただの公式の書写しじゃなくてこちら側の見解とか、読者のためになる情報に」。scripts/own_view.py）

しきい値を決めたときの測定（2026-11-12・直近7日の記事 532本・暮らしとお金 319本）:
  本文1,000字未満: 暮らしとお金の37%（119本）→ 公式の資料で1回書き足す対象（EXPAND_BELOW）
  本文500字未満で速報・注意喚起でない: 暮らしとお金の7.5%（24本）・全体の6.2%（33本）→ 書き足してもこの長さなら保留（HOLD_BELOW。上限の見込み）
  600字にすると暮らしとお金の11.9%（38本）で、許容（約10%）を超える
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import own_view  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

FACTS = ("個人向け国債の固定5年の利率は年2.17%です。前回の募集より0.22ポイント下がりました。"
         "申し込みは11月30日まで、取扱金融機関で受け付けます。発行日は12月15日です。")
LONG = FACTS * 13  # 約1,130字（書き足しの対象にならない長さ）
MID = FACTS * 7  # 約610字（保留の下限より長く、書き足しの対象）
VIEW = ("## サイソクの見方：急がないなら固定5年、1年以内に使うなら見送り\n\n"
        "固定5年の年2.17%は前回より0.22ポイント低く、利率の高さだけで選ぶ理由は弱まったとみられます。"
        "5年使う予定の無いお金なら固定5年、1年以内に使うかもしれないお金なら見送るのが目安です。\n")


def life_record(body: str, **extra) -> dict:
    return {"title": "個人向け国債、11月募集の固定5年は年2.17%", "genreSlug": "public", "newsType": "policy", "body": body, **extra}


class FakeLLM:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, system, prompt, schema, **kw):
        self.calls.append((prompt, schema, kw))
        return self.answers.pop(0), "fake-model"


class PromptTest(unittest.TestCase):
    def test_rule_asks_for_three_parts_labeled_and_grounded(self):
        rule = own_view.prompt_block()
        for word in ("## サイソクの見方：", "なぜ今か", "誰が得をし", "（サイソク編集部の計算）", "〜ならA、〜ならB", "事実のように断定しない",
                     "新しい事実・数字を足さない", "特定の会社・商品をすすめる"):
            self.assertIn(word, rule)
        self.assertNotIn("｜", rule)
        self.assertNotIn("ざっくり", rule)

    def test_every_writing_path_gets_the_rule(self):
        import web_articles as w  # noqa: PLC0415

        item = {"source_name": "財務省", "title": "個人向け国債の利率", "published_at": datetime.now(timezone.utc), "url": "https://www.mof.go.jp/a"}
        self.assertIn(own_view.PROMPT_RULE, w.build_prompt(item, "本文"))
        self.assertIn(own_view.PROMPT_RULE, w.build_broad_prompt(item, "本文", w.GENRES_BY_SLUG["public"]))
        self.assertIn(own_view.PROMPT_RULE, w.build_trend_prompt({"title": "国債", "summary": ""}, [{"url": "https://example.com", "text": "t"}],
                                                                 w.GENRES_BY_SLUG["public"]))
        self.assertIn("サイソクの見方", w.WEB_SOURCE_NOTE)
        # 動画（main）・Muse・深掘りの経路
        self.assertIn("own_view.prompt_block()", (ROOT / "scripts" / "main.py").read_text("utf-8"))
        import muse_articles  # noqa: PLC0415
        import muse_format  # noqa: PLC0415

        self.assertIn("サイソクの見方", muse_articles.MUSE_DRAFT_NOTE)
        self.assertIn("## サイソクの見方：", muse_format.FORMAT_MD)
        self.assertIn("own_view.ensure", (ROOT / "scripts" / "deep_dive.py").read_text("utf-8"))
        self.assertIn("own_view.ensure", (ROOT / "scripts" / "muse_articles.py").read_text("utf-8"))

    def test_honest_voice_no_longer_limits_view_to_two_sentences(self):
        import main as m  # noqa: PLC0415

        honest = dict(m.VOICES)["honest"]
        self.assertIn("サイソクの見方", honest)
        self.assertNotIn("1〜2文だけ", honest)

    def test_fact_check_treats_labeled_view_as_interpretation_but_checks_its_numbers(self):
        import quality  # noqa: PLC0415

        self.assertIn("サイソクの見方", quality.FACT_PROMPT)
        self.assertIn("根拠の無い見通し", quality.WEB_USEFULNESS_PROMPT)


class ViewCheckTest(unittest.TestCase):
    def test_present_with_judgement(self):
        rec = life_record(FACTS + "\n\n" + VIEW)
        self.assertEqual(own_view.view_problems(rec), [])
        self.assertIn("固定5年", own_view.view_section(rec["body"]))

    def test_absent(self):
        problems = own_view.view_problems(life_record(FACTS))
        self.assertEqual(len(problems), 1)
        self.assertIn("サイソクの見方", problems[0])

    def test_inline_editor_view_is_not_enough(self):
        # 今までの「編集部の見方では…」の1文だけは、章として数えない（読者の判断の目安の章が要る）
        self.assertTrue(own_view.view_problems(life_record(FACTS + "編集部の見方では、利率は下がりました。")))

    def test_present_without_judgement(self):
        body = FACTS + "\n\n## サイソクの見方：利率は2回続けて下がった\n\n固定5年の年2.17%は前回より0.22ポイント低い水準です。発行日は12月15日とされています。\n"
        problems = own_view.view_problems(life_record(body))
        self.assertTrue(any("判断の目安" in p for p in problems))

    def test_required_only_for_life_and_money(self):
        self.assertTrue(own_view.required(life_record(FACTS)))
        self.assertFalse(own_view.required({**life_record(FACTS), "genreSlug": "ai"}))
        self.assertFalse(own_view.required({**life_record(FACTS), "title": "財務大臣、ベトナム財政大臣と面会"}))


class RepairTest(unittest.TestCase):
    def test_missing_view_is_added_once_before_unknowns(self):
        body = LONG + "\n\n## まだ分からないこと\n\n- 12月の利率はまだ発表されていません。\n"
        rec = life_record(body)
        fake = FakeLLM({"view_markdown": VIEW})
        notes = own_view.ensure(rec, FACTS, log=lambda _: None, generate=fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][1], own_view.VIEW_SCHEMA)
        self.assertEqual(own_view.view_problems(rec), [])
        self.assertLess(rec["body"].index("## サイソクの見方"), rec["body"].index("## まだ分からないこと"))
        self.assertTrue(rec.get("ownViewAdded"))
        self.assertTrue(any("足した" in n for n in notes))

    def test_view_with_numbers_not_in_source_is_not_used(self):
        rec = life_record(LONG)
        bad = VIEW.replace("0.22ポイント", "0.35ポイント")
        own_view.ensure(rec, FACTS, log=lambda _: None, generate=FakeLLM({"view_markdown": bad}))
        self.assertNotIn("サイソクの見方", rec["body"])
        self.assertIsNotNone(own_view.hold_reason(rec))

    def test_thin_body_expanded_with_source_facts_then_view(self):
        rec = life_record(FACTS)
        longer = (FACTS + "\n\n") * 13
        fake = FakeLLM({"body_markdown": longer}, {"view_markdown": VIEW})
        own_view.ensure(rec, FACTS, log=lambda _: None, generate=fake)
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(fake.calls[0][1], own_view.BODY_SCHEMA)
        self.assertGreater(len(rec["body"]), len(FACTS) * 12)
        self.assertEqual(own_view.view_problems(rec), [])
        self.assertIsNone(own_view.hold_reason(rec))

    def test_expansion_that_invents_numbers_is_dropped(self):
        rec = life_record(FACTS)
        fake = FakeLLM({"body_markdown": LONG + "利用者は約300万人です。"}, {"view_markdown": VIEW})
        own_view.ensure(rec, FACTS, log=lambda _: None, generate=fake)
        self.assertNotIn("300万人", rec["body"])

    def test_llm_failure_does_not_raise(self):
        def boom(*a, **k):
            raise RuntimeError("down")

        rec = life_record(LONG)
        notes = own_view.ensure(rec, FACTS, log=lambda _: None, generate=boom)
        self.assertTrue(any("失敗" in n for n in notes))

    def test_nothing_to_do_makes_no_call(self):
        rec = life_record(LONG + "\n\n" + VIEW)
        fake = FakeLLM()
        self.assertEqual(own_view.ensure(rec, FACTS, generate=fake), [])
        self.assertEqual(fake.calls, [])


class UrgentExemptTest(unittest.TestCase):
    def test_breaking_and_fast_articles_are_not_touched_or_held(self):
        for rec, urgent in ((life_record(FACTS), True), (life_record(FACTS, breaking=True), False),
                            (life_record(FACTS, newsType="breaking"), False), (life_record(FACTS, disaster=True), False)):
            fake = FakeLLM()
            self.assertEqual(own_view.ensure(rec, FACTS, urgent=urgent, generate=fake), [])
            self.assertEqual(fake.calls, [])
            self.assertIsNone(own_view.hold_reason(rec, urgent=urgent))

    def test_alert_gets_view_but_no_expansion_and_is_never_held(self):
        rec = {"title": "ドコモを名乗る詐欺のSMSに注意喚起　偽のサイトに誘導", "genreSlug": "public", "newsType": "security", "body": FACTS}
        self.assertTrue(own_view.short_alert(rec))
        self.assertEqual(own_view.needs(rec), {"view": True, "expand": False})
        fake = FakeLLM({"view_markdown": "## サイソクの見方：届いたなら開かない\n\n" + "届いたSMSのリンクを開いた場合は、11月30日までに取扱金融機関で確かめる目安です。" * 2})
        own_view.ensure(rec, FACTS, log=lambda _: None, generate=fake)
        self.assertEqual(len(fake.calls), 1)
        rec["body"] = FACTS  # 章を足せなかったとしても
        self.assertIsNone(own_view.hold_reason(rec))


class HoldTest(unittest.TestCase):
    def test_short_life_article_is_held(self):
        why = own_view.hold_reason(life_record("日銀は9月の預金者別預金を公表しました。" + "\n\n" + VIEW))
        self.assertIn("中身が足りない", why)

    def test_life_article_without_view_is_held(self):
        why = own_view.hold_reason(life_record(MID))
        self.assertIn("サイソクの見方", why)

    def test_good_life_article_passes(self):
        self.assertIsNone(own_view.hold_reason(life_record(MID + "\n\n" + VIEW)))

    def test_ai_article_without_view_passes_but_short_one_is_held(self):
        ai = {"title": "新しいモデルを公開", "genreSlug": "ai", "newsType": "product"}
        self.assertIsNone(own_view.hold_reason({**ai, "body": MID}))
        self.assertIsNotNone(own_view.hold_reason({**ai, "body": FACTS}))

    def test_thresholds(self):
        self.assertEqual(own_view.EXPAND_BELOW, 1000)
        self.assertEqual(own_view.HOLD_BELOW, 500)


class WebGateWiringTest(unittest.TestCase):
    def test_gate_calls_ensure_before_fact_check_and_hold_in_finish(self):
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        gated = src[src.index("    def gated("):src.index("    def try_followup(")]
        self.assertLess(gated.index("own_view.ensure("), gated.index("quality.evaluate("))
        finish = src[src.index("    def finish("):src.index("    def rescue_draft(")]
        self.assertIn("own_view.hold_reason(record, urgent=view_urgent(item))", finish)

    def test_view_urgent(self):
        import quality  # noqa: PLC0415
        import web_articles as w  # noqa: PLC0415

        self.assertTrue(w.view_urgent({"fast": True}))
        self.assertFalse(w.view_urgent({}))
        quality.MAJOR = True
        try:
            self.assertTrue(w.view_urgent({}))
        finally:
            quality.MAJOR = False


if __name__ == "__main__":
    unittest.main()
