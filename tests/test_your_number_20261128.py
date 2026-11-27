"""あなたの数字の門（2026-11-28 見直し。scripts/your_number.py）

試し（2026-11-28・直近3日の公開記事98本。LLM なし）: 軸の記事（家計のお金・注意）50本のうち、4つがそろっていた記事 29本、
手直しが要る記事 21本（足りないもの a 13・b 5・c 3）。無料モデルでの手直しの試し 8本のうち 4本が4つそろった（残りは資料に材料が無いか、
資料に無い数字・URL が出たので使わなかった）。
"""
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quality_bar as qb  # noqa: E402
import weekly_quality_sample as wq  # noqa: E402
import your_number as yn  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

SOURCE = ("日本年金機構 年金生活者支援給付金のお知らせ https://www.nenkin.go.jp/service/kyufukin/index.html\n"
          "令和8年度の給付基準額は月5,620円です。保険料を納めた月数に応じて計算します。請求書は年金事務所に提出してください。"
          "請求の期限は令和9年3月31日です。https://www.nenkin.go.jp/service/kyufukin/seikyu.html")

GOOD = """年金を受け取っている人は、12月15日の振込から給付金を受け取れます（日本年金機構）。請求の期限は令和9年3月31日です。

## 納めた月数で、もらえる額が変わる

| 納めた月数 | 月額の目安 |
|---|---|
| 480か月 | 5,620円 |
| 240か月 | 2,810円 |

## 請求は年金事務所で、令和9年3月31日まで

請求書は年金事務所に出してください（[日本年金機構の案内](https://www.nenkin.go.jp/service/kyufukin/seikyu.html)）。

## サイソクの見方：請求を忘れずに

月5,620円は1年で6万7,440円です。
"""


def rec(**kw) -> dict:
    base = {"slug": "kyufukin", "title": "年金生活者支援給付金の請求は3月31日まで", "genreSlug": "public",
            "lede": "年金を受け取っている人は給付金を請求できます。", "body": GOOD,
            "sourceUrl": "https://www.nenkin.go.jp/service/kyufukin/index.html", "sourceName": "日本年金機構",
            "publishedAt": "2026-11-27T03:00:00+00:00"}
    base.update(kw)
    return base


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def __call__(self, system, prompt, schema, **kw):
        self.calls += 1
        assert kw.get("purpose") == "repair"  # 月の予算の救済の段（OpenAI が先の設定なら GPT のクレジット）
        return self.answer, "fake-model"


class TopicGateTest(unittest.TestCase):
    def test_axis_topics(self):
        cases = {
            "年金生活者支援給付金、12月から月400円増える": "money",
            "児童手当の12月の支給日は？": "money",
            "2027年1月分電気料金の燃料費等調整単価をお知らせします": "money",
            "任意継続の12月分保険料は12月10日まで": "money",
            "リコールの届出について（スバル フォレスター 他）": "alert",
            "ピーチの個人情報、最大約944万件が流出": "alert",
            "無登録で金融商品取引業を行う者の名称等について更新しました": "alert",
            "震度5強の地震　津波の心配なし": "safety",
            "台風10号、九州に接近": "safety",
        }
        for title, kind in cases.items():
            with self.subTest(title=title):
                self.assertEqual(yn.topic_kind(title), kind)

    def test_off_axis_topics(self):
        for title, section in (
            ("張本美和に中国でアンチが少ないのはなぜ？", "sports"),
            ("Netflix映画「クロス・ミッション2」は12月25日に公開", "entertainment"),
            ("応答は最大1.8倍速い無料AIモデル「Mellum2.1 Instruct」を公開", "ai"),
            ("レクサス「NX」新型は12月7日発売", "business"),
            ("トヨタ、第2四半期決算は増収増益", "business"),
            ("食品輸出のセミナー、東海3県向けに開催　申込は12月7日まで", "business"),
            ("採用情報（任期付職員（発達障害施策調整官）募集情報）", "public"),
            ("第139回社会保障審議会介護保険部会の資料について", "public"),
            ("高市総理はマーシャル諸島共和国の大統領と首脳会談を行いました", "public"),
        ):
            with self.subTest(title=title):
                self.assertIsNone(yn.topic_kind(title, section=section))

    def test_corporate_news_with_household_money_is_axis(self):
        self.assertEqual(yn.topic_kind("ドコモSMTBネット銀行、円定期預金の金利を改定", section="investment"), "money")
        self.assertEqual(yn.topic_kind("新日本プロレスがABEMAで月額850円　2027年4月から980円に", section="entertainment"), "money")

    def test_foreign_items_only_for_outages_and_breaches(self):
        self.assertIsNone(yn.topic_kind("Introducing GPT-6.2", lang="en"))
        self.assertEqual(yn.topic_kind("Cloudflare outage on November 18", lang="en"), "alert")

    def test_topic_block_and_switches(self):
        off = {"title": "MLBのロックアウト懸念と大型契約", "section": "sports", "lang": "ja", "url": "https://example.jp/mlb"}
        with mock.patch.dict(os.environ, {"AXIS_TOPIC_GATE": "1"}):
            self.assertIsNone(yn.topic_block({"title": "児童手当の支給日", "section": "public", "lang": "ja"}))
            self.assertEqual(yn.topic_block(off), yn.TOPIC_REASON)
            self.assertEqual(yn.topic_block(off, breaking=True), yn.TOPIC_REASON)  # 速報の候補でも、安全・注意・お金でなければ作らない
            with mock.patch.dict(os.environ, {"AXIS_GATE_BREAKING": "0"}):
                self.assertIsNone(yn.topic_block(off, breaking=True))
                self.assertEqual(yn.topic_block(off), yn.TOPIC_REASON)
        with mock.patch.dict(os.environ, {"AXIS_TOPIC_GATE": "0"}):
            self.assertIsNone(yn.topic_block(off))

    def test_default_mode_only_logs(self):
        """2026-11-28 オーナー「本数を減らさない」: 既定は止めずに記録だけ（同じ候補は1回）"""
        off = {"title": "MLBのロックアウト懸念と大型契約", "section": "sports", "lang": "ja", "url": "https://example.jp/mlb"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(yn, "TOPIC_LOG_PATH", Path(tmp) / "t.json"), \
                mock.patch.dict(os.environ, {"YOUR_NUMBER_LOG": "1"}):
            os.environ.pop("AXIS_TOPIC_GATE", None)
            self.assertEqual(yn.topic_mode(), "log")
            lines = []
            self.assertIsNone(yn.topic_block(off, log=lines.append))
            self.assertIsNone(yn.topic_block(off, log=lines.append))
            self.assertEqual(len(lines), 2)
            self.assertEqual(len(json.loads((Path(tmp) / "t.json").read_text("utf-8"))), 1)

    def test_every_auto_path_calls_the_topic_gate(self):
        web = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        pick = web[web.index("    def _pick(cand"):]
        pick = pick[: pick.index("\n    def ", 10)]
        # 最初の門（大きなニュース・速報・話題のレーン・ふつうのレーンのすべてが通る）
        self.assertLess(pick.index("your_number.topic_block("), pick.index("if major and not cap_free(cand)"))
        main = (ROOT / "scripts" / "main.py").read_text("utf-8")
        self.assertLess(main.index("your_number.topic_block("), main.index("data = generate_article(client, entry)"))


class ContentGateTest(unittest.TestCase):
    def test_good_article_has_all_four(self):
        self.assertEqual(yn.check(rec())["missing"], [])

    def test_each_requirement(self):
        no_table = GOOD.replace("| 480か月 | 5,620円 |\n| 240か月 | 2,810円 |\n", "").replace("| 納めた月数 | 月額の目安 |\n|---|---|\n", "")
        self.assertIn("a", yn.check(rec(body=no_table))["missing"])
        no_date = GOOD.replace("12月15日の振込から", "").replace("請求の期限は令和9年3月31日です。", "").replace("、令和9年3月31日まで", "")
        self.assertIn("b", yn.check(rec(body=no_date, lede="給付金を請求できます。"))["missing"])
        no_url = GOOD.replace("（[日本年金機構の案内](https://www.nenkin.go.jp/service/kyufukin/seikyu.html)）", "")
        self.assertIn("c", yn.check(rec(body=no_url))["missing"])
        # 窓口の欄（officialDesk）に公式の URL があれば c は足りる
        self.assertNotIn("c", yn.check(rec(body=no_url, officialDesk=[{"name": "日本年金機構", "url": "https://www.nenkin.go.jp/"}]))["missing"])
        self.assertIn("d", yn.check(rec(sourceUrl="https://www.nikkei.com/article/x"))["missing"])
        self.assertIn("d", yn.check(rec(pressReport=True))["missing"])

    def test_no_deadline_statement_counts(self):
        body = GOOD.replace("12月15日の振込から", "").replace("請求の期限は令和9年3月31日です。", "手続きは不要です。").replace("、令和9年3月31日まで", "")
        self.assertNotIn("b", yn.check(rec(body=body, lede="給付金は自動で振り込まれます。"))["missing"])

    def test_alert_needs_a_way_to_check(self):
        body = ("ルノーのカングー324台がリコールの対象です。11月27日に国土交通省に届け出ました。\n\n"
                "## 販売店で無料で交換\n\n販売店に問い合わせてください（[国土交通省](https://www.mlit.go.jp/report/press/x.html)）。\n")
        r = rec(title="「カングー」324台がリコール対象　冷却水漏れのおそれ", body=body, sourceUrl="https://www.mlit.go.jp/report/press/x.html")
        self.assertEqual(yn.check(r)["kind"], "alert")
        self.assertIn("a", yn.check(r)["missing"])
        fixed = body + "\n## 対象の車の確かめ方\n\n- 型式：3DA-KFKK9K\n- 製作期間：令和6年9月10日から令和7年7月8日まで\n"
        self.assertEqual(yn.check({**r, "body": fixed})["missing"], [])

    def test_own_amount_lookup_counts_for_a(self):
        body = ("任意継続の人は、12月分の保険料を12月10日までに納めます。\n\n## 納付書で額を確かめる\n\n"
                "保険料の額は、届いた納付書で確かめられます（[協会けんぽ](https://www.kyoukaikenpo.or.jp/x)）。窓口は各支部です。\n")
        r = rec(title="任意継続の12月分保険料は12月10日まで", body=body, sourceUrl="https://www.kyoukaikenpo.or.jp/x")
        self.assertEqual(yn.check(r)["missing"], [])

    def test_off_axis_and_safety_are_not_checked(self):
        self.assertFalse(yn.check(rec(title="レクサス「NX」新型は12月7日発売", genreSlug="business", body="新型です。"))["applies"])
        quake = rec(title="震度5強の地震", body="揺れました。")
        self.assertFalse(yn.check(quake)["applies"])
        self.assertTrue(yn.urgent_record(quake))


class CalculatorTest(unittest.TestCase):
    def test_python_calculators_match_lib(self):
        ts = (ROOT / "lib" / "calculators.ts").read_text("utf-8")
        kinds = set(re.findall(r'"([a-z-]+)"', re.search(r"export type CalculatorKind = ([^;]+);", ts).group(1)))
        self.assertEqual(kinds, set(yn.CALCULATORS))
        self.assertEqual(set(yn.CALC_ORDER), kinds)
        for kind, (href, _title, _rx) in yn.CALCULATORS.items():
            self.assertIn(f'href: "{href}"', ts, kind)

    def test_calculator_link_is_added_near_the_top_without_llm(self):
        body = ("3歳未満の子は月1万5千円です。\n\n## 支給日は12月10日\n\n12月10日に市区町村から振り込まれます。\n\n## 申請は市区町村の窓口で\n\n"
                "窓口で手続きします（[こども家庭庁](https://www.cfa.go.jp/policies/kokoseido/jidouteate)）。\n")
        r = rec(title="児童手当の12月の支給日は？", body=body, sourceUrl="https://www.cfa.go.jp/policies/kokoseido/jidouteate")
        self.assertEqual(yn.check(r)["missing"], ["a"])
        fake = FakeLLM({"number_markdown": "", "desk_markdown": "", "replacements": []})
        result = yn.ensure(r, SOURCE, log=lambda *_: None, generate=fake)
        self.assertEqual(result["missing"], [])
        self.assertEqual(fake.calls, 0)  # プログラムで足りたので LLM を呼ばない
        self.assertLess(r["body"].index("/tools/child-allowance"), r["body"].index("## 支給日は12月10日"))
        self.assertNotRegex(r["body"], "\\*\\*|｜|→")

    def test_prompt_mentions_the_matching_calculator(self):
        self.assertIn("/tools/child-allowance", qb.prompt_block("児童手当の12月の支給日は？"))
        self.assertIn("あなたの数字のニュース", qb.prompt_block(""))
        self.assertNotIn("/tools/child-allowance", qb.prompt_block("リコールの届出について"))


class RepairTest(unittest.TestCase):
    def no_table(self):
        return rec(body=GOOD.replace("| 納めた月数 | 月額の目安 |\n|---|---|\n| 480か月 | 5,620円 |\n| 240か月 | 2,810円 |\n", "かかります。\n"),
                   title="障害年金の請求は3月31日まで")

    def test_repair_adds_the_table_from_the_source(self):
        r = self.no_table()
        self.assertEqual(yn.check(r)["missing"], ["a"])
        table = "## 納めた月数で月額が変わる\n\n| 納めた月数 | 月額 |\n|---|---|\n| 480か月 | 5,620円 |\n| 240か月 | 2,810円 |"
        result = yn.ensure(r, SOURCE + " 480か月 240か月 2,810円", log=lambda *_: None,
                           generate=FakeLLM({"number_markdown": table, "desk_markdown": "", "replacements": []}))
        self.assertEqual(result["missing"], [])
        self.assertTrue(r["yourNumber"]["repaired"])
        self.assertLess(r["body"].index("## 納めた月数で月額が変わる"), r["body"].index("## 請求は年金事務所で"))

    def test_invented_numbers_or_urls_are_not_used(self):
        for patch in ({"number_markdown": "## 月額\n\n| 月数 | 月額 |\n|---|---|\n| 480か月 | 9,999円 |\n| 120か月 | 1,405円 |",
                       "desk_markdown": "", "replacements": []},
                      {"number_markdown": "## 月額の確かめ方\n\n年金額は、ねんきんネットのページで確かめられます（https://www.nenkin.go.jp/invented/page）。",
                       "desk_markdown": "", "replacements": []}):
            r = self.no_table()
            body = r["body"]
            notes = []
            yn.ensure(r, SOURCE, log=notes.append, generate=FakeLLM(patch))
            with self.subTest(patch=str(patch)[:40]):
                self.assertEqual(r["body"], body)
                self.assertTrue(any("使わない" in n for n in notes), notes)

    def test_top_page_of_a_known_site_is_allowed(self):
        self.assertEqual(yn.new_urls("https://www.nenkin.go.jp を見る", SOURCE), set())
        self.assertEqual(yn.new_urls("https://www.example.go.jp/x", SOURCE), {"https://www.example.go.jp/x"})

    def test_urgent_records_are_not_repaired_with_llm_but_marked(self):
        r = self.no_table()
        r["breaking"] = True
        fake = FakeLLM({"number_markdown": "", "desk_markdown": "", "replacements": []})
        yn.ensure(r, SOURCE, log=lambda *_: None, generate=fake)
        self.assertEqual(fake.calls, 0)
        self.assertTrue(r["yourNumber"]["repairLater"])
        self.assertIsNone(yn.hold_reason(r))

    def test_llm_failure_does_not_raise(self):
        def boom(*a, **k):
            raise RuntimeError("down")
        r = self.no_table()
        notes = []
        yn.ensure(r, SOURCE, log=notes.append, generate=boom)
        self.assertTrue(any("失敗" in n for n in notes))


class HoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patcher in (mock.patch.object(yn, "LOG_PATH", Path(self.tmp.name) / "log.json"),
                        mock.patch.dict(os.environ, {"YOUR_NUMBER_LOG": "1"})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_axis_article_missing_after_repair_is_held_and_logged(self):
        r = rec(body="給付金があります。\n")
        reason = yn.hold_reason(r)
        self.assertIn("あなたの数字の門", reason)
        rows = json.loads((Path(self.tmp.name) / "log.json").read_text("utf-8"))
        self.assertEqual(rows[-1]["slug"], "kyufukin")
        self.assertTrue(rows[-1]["missing"])
        # 公開の前の最後の門（quality_bar.hold_reason）からも止まる（ジャンルにかかわらず）
        self.assertIn("あなたの数字の門", qb.hold_reason({**r, "genreSlug": "tech-gadget"}))

    def test_good_off_axis_and_switch(self):
        self.assertIsNone(yn.hold_reason(rec()))
        self.assertIsNone(yn.hold_reason(rec(title="MLBのロックアウト懸念", genreSlug="sports", body="x")))
        with mock.patch.dict(os.environ, {"AXIS_CONTENT_GATE": "0"}):
            self.assertIsNone(yn.hold_reason(rec(body="給付金があります。\n")))
        self.assertEqual(len(json.loads((Path(self.tmp.name) / "log.json").read_text("utf-8"))), 1)  # 止めないときも記録は残す


class WeeklySampleTest(unittest.TestCase):
    def test_report_in_plain_japanese(self):
        now = datetime(2026, 11, 28, 3, tzinfo=timezone.utc)
        arts = [rec(slug=f"k{i}", publishedAt=(now - timedelta(days=i % 6)).isoformat()) for i in range(14)]
        arts.append(rec(slug="old", publishedAt=(now - timedelta(days=20)).isoformat()))
        arts.append(rec(slug="sports", title="MLBのロックアウト懸念", genreSlug="sports", publishedAt=now.isoformat()))
        with mock.patch.object(qb, "_CORPUS", qb.corpus([])):
            text = wq.report(arts, now, k=10, seed=1)
        self.assertIn("記事の質の抜き取り", text)
        self.assertEqual(text.count("\n### "), 10)
        self.assertIn("公開した記事: 15 本", text)
        self.assertNotIn("/articles/old", text)
        self.assertNotRegex(text, "\\*\\*|｜|→|ざっくり")

    def test_weekly_workflow_runs_it(self):
        wf = (ROOT / ".github" / "workflows" / "weekly.yml").read_text("utf-8")
        self.assertIn("python scripts/weekly_quality_sample.py", wf)
        self.assertIn("git add state/quality_weekly", wf)


if __name__ == "__main__":
    unittest.main()
