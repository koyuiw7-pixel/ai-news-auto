"""「かんたんに読む」版の作り直し（scripts/easy_version.py。2026-11-10 オーナー指摘: Muse の記事で切り替えが消えていた）"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import easy_version as ev  # noqa: E402

BODY = (
    "値引きが入っていたのは、2026年9月使用分（10月分の請求）までです。11月分からは、値引きがない金額に戻ります。"
    "申請や手続きは要りません。値引きは、契約している事業者が自動的に処理していました。\n\n"
    "## 対象になるのは家庭向けの低圧契約\n\n"
    "東京電力の平均モデルでは、10月分は8,275円でした。11月分は9,561円で、前月との差は1,286円です。"
    "冬の支援の対象は、一般家庭と年間契約量1,000万立方メートル未満の企業等です。プロパンガスは対象外です。\n\n"
    "## 冬の支援は12月使用分から\n\n"
    "支援の実施期間は、2026年12月使用分から2027年2月使用分までです。低圧で12月使用分が1.0円/kWhです。"
    "問い合わせ窓口は0120-013-305で、受付時間は平日9時から17時です。"
)
SUMMARY_ONLY = "## ひとことで言うと\n\n国の支援による電気代の値引きが、11月分の請求で終わります。"
GOOD = """## ひとことで言うと
国の電気代の値引きが終わり、11月分の請求から電気代が上がります。

## 11月分から値引きがなくなる
値引きが入っていたのは10月分の請求までです。東京電力の平均モデルでは、11月分は9,561円になりました。

## 家庭向けの低圧契約が対象
対象は一般家庭などです。プロパンガスは対象外です。

## 冬の支援は12月使用分から
冬の支援は2026年12月使用分から戻ります。低圧で12月使用分は1.0円/kWhです。

## 申請はいらない
申請や手続きは要りません。契約している事業者が自動で処理します。
"""


def record(easy=SUMMARY_ONLY, **extra):
    return {"title": "電気代の値引きが終わる", "body": BODY, "easy": easy, "highlights": ["a", "b"], "museFile": "x.md", **extra}


class ThinTest(unittest.TestCase):
    def test_summary_only_easy_is_thin_when_highlights_exist(self):
        # 記事ページは要点がある記事で「ひとことで言うと」の章を出さない → 空になり切り替えが消える
        self.assertTrue(ev.thin(record()))
        self.assertEqual(ev.visible_easy(record()), "")

    def test_summary_kept_without_highlights(self):
        self.assertIn("値引き", ev.visible_easy(record(highlights=[])))

    def test_real_easy_is_not_thin(self):
        self.assertFalse(ev.thin(record(easy=GOOD)))

    def test_three_reported_muse_articles_are_detected_or_fixed(self):
        import json

        for slug in ("electricity-bill-nov-2026-subsidy-ends", "child-allowance-december-payment",
                     "pension-support-benefit-old-age-eligibility"):
            path = ROOT / "content" / "articles" / f"{slug}.json"
            if not path.exists():
                continue
            rec = json.loads(path.read_text("utf-8"))
            # まだ直していなければ thin、直した後は表示に中身がある（どちらかでなければ、この段が見落としている）
            self.assertTrue(ev.thin(rec) or len(ev._plain(ev.visible_easy(rec))) >= ev.EASY_MIN_CHARS, slug)


class CheckTest(unittest.TestCase):
    def test_good_easy_passes_without_llm(self):
        problems, _ = ev.check(record(), GOOD, facts=False)
        self.assertEqual(problems, [])

    def test_number_not_in_body_is_rejected(self):
        bad = GOOD.replace("9,561円", "9,999円")
        self.assertTrue(any("本文に無い数字" in p for p in ev.number_problems(bad, BODY)))

    def test_computed_number_is_rejected(self):
        # 自分で計算した数字（年額など）も認めない
        bad = GOOD + "\n1年で15,432円の負担増です。\n"
        self.assertTrue(ev.number_problems(bad, BODY))

    def test_summary_only_is_rejected(self):
        problems, _ = ev.check(record(), SUMMARY_ONLY, facts=False)
        self.assertTrue(any("2つ以上" in p for p in problems))

    def test_question_heading_and_bar_rejected(self):
        problems, _ = ev.check(record(), GOOD.replace("## 申請はいらない", "## 自分に関係ある？").replace("対象は", "対象は｜"), facts=False)
        self.assertTrue(any("？" in p for p in problems))
        self.assertTrue(any("｜" in p for p in problems))

    def test_fact_check_failure_rejects(self):
        import quality

        with patch.object(quality, "fact_check", return_value={"grounded": False, "fatal": True, "score": 40, "problems": ["創作"]}):
            problems, _ = ev.check(record(), GOOD)
        self.assertTrue(any("事実確認" in p for p in problems))


class EnsureTest(unittest.TestCase):
    def test_llm_failure_leaves_article_as_is(self):
        import llm

        rec = record()
        with patch.object(llm, "generate_json", side_effect=RuntimeError("no model")):
            status = ev.ensure(rec)
        self.assertTrue(status.startswith("fail"))
        self.assertEqual(rec["easy"], SUMMARY_ONLY)

    def test_unverified_draft_is_not_used(self):
        import llm

        rec = record()
        with patch.object(llm, "generate_json", return_value=({"easy_markdown": GOOD.replace("9,561円", "9,999円")}, "m")):
            status = ev.ensure(rec)
        self.assertTrue(status.startswith("fail"))
        self.assertEqual(rec["easy"], SUMMARY_ONLY)

    def test_verified_draft_is_used(self):
        import llm
        import quality

        rec = record()
        with patch.object(llm, "generate_json", return_value=({"easy_markdown": GOOD}, "m")), \
                patch.object(quality, "fact_check", return_value={"grounded": True, "fatal": False, "score": 95, "problems": []}):
            status = ev.ensure(rec)
        self.assertTrue(status.startswith("ok"), status)
        self.assertFalse(ev.thin(rec))

    def test_not_thin_is_skipped(self):
        self.assertEqual(ev.ensure(record(easy=GOOD)), "skip")


class WiringTest(unittest.TestCase):
    def test_muse_ingest_runs_easy_version(self):
        src = (ROOT / "scripts" / "muse_articles.py").read_text("utf-8")
        self.assertIn("easy_version.ensure(record", src)

    def test_backfill_workflow(self):
        text = (ROOT / ".github" / "workflows" / "easy_backfill.yml").read_text("utf-8")
        self.assertIn("scripts/easy_version.py --wide --apply", text)
        self.assertIn("CLAUDE_API_LEDGER: easy", text)
        self.assertIn("git_safe_push.py --wait-idle auto_run.yml", text)
        import llm

        self.assertIn("easy", llm.MAINTENANCE_LEDGERS)


class WideTargetTest(unittest.TestCase):
    def _run(self, records, noindex=(), retired=(), views=None):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            art = Path(d)
            for r in records:
                (art / f"{r['slug']}.json").write_text(json.dumps(r, ensure_ascii=False), "utf-8")
            files = {
                "noindex_zero_visit.json": {"slugs": list(noindex)},
                "retired.json": {"articles": {s: {} for s in retired}},
                "popular.json": {"items": [{"slug": k, "views": v} for k, v in (views or {}).items()]},
            }
            with patch.object(ev, "ARTICLES_DIR", art), patch.object(ev, "_load_json", lambda n: files.get(n, {})):
                args = type("A", (), {"slug": "", "muse": False, "wide": True})()
                return [p.stem for p in ev.targets(args)]

    def test_wide_order_and_exclusions(self):
        def rec(slug, genre, at):
            return record(slug=slug, genre=genre, publishedAt=at, body=BODY)

        got = self._run(
            [
                rec("tech-new", "AI・テクノロジー", "2026-11-09"),
                rec("life-old", "暮らし・生活", "2026-10-01"),
                rec("life-new", "暮らし・生活", "2026-11-05"),
                rec("seen-tech", "AI・テクノロジー", "2026-09-01"),
                rec("noindexed", "暮らし・生活", "2026-11-08"),
                rec("gone", "暮らし・生活", "2026-11-08"),
            ],
            noindex=["noindexed"],
            retired=["gone"],
            views={"seen-tech": 5},
        )
        self.assertEqual(got, ["seen-tech", "life-new", "life-old", "tech-new"])


if __name__ == "__main__":
    unittest.main()
