"""発表時刻が決まった速報（統計・決算）の見張りと門（2026-11-05 オーナー承認・台帳 W35）。

オーナーの決まり: 速さで質を落とさない。数字は公式の資料そのものから。読めなければ速報にしない。
ネットには出ない（取得はすべて差し替える）。
"""
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fast_lane  # noqa: E402
import notice_gate  # noqa: E402
import pdf_text  # noqa: E402
import quality  # noqa: E402
import release_quality  # noqa: E402
import release_watch as rw  # noqa: E402

# 厚労省の報道発表資料（2025年9月分速報）の形を写した材料（数字は資料の書き方のまま）
MAIKIN = """毎月勤労統計調査 2026(令和8)年9月分結果速報等 を公表します
※2 速報値は、確報で改訂される場合があります。
【調査結果のポイント】 ※1 ()内は前年同月比を示す。
1 名目賃金(一人平均)
・現金給与総額〔規模5人以上〕 297,145 円(1.9%増)※45 ヵ月連続プラス
・きまって支給する給与 287,840 円(1.8%増)※47 ヵ月連続プラス
2 実質賃金指数(2020(令和2)年平均=100)
〇消費者物価指数(持家の帰属家賃を除く総合)で実質化したもの
・現金給与総額 81.8(1.4%減)※9 ヵ月連続マイナス
(参考)消費者物価指数(持家の帰属家賃を除く総合)の前年同月比 3.4%上昇
3 夏季賞与(※毎年9月の速報に併せて掲載)
・支給事業所における労働者一人平均賞与額〔規模5人以上〕 426,337 円(2.9%増)
""" + "実質賃金と名目賃金の説明。" * 40


def maikin_event():
    return next(e for e in rw.load_calendar()["events"] if e["id"] == "maikin-2026-09")


class CalendarTest(unittest.TestCase):
    def test_workflow_crons_match_the_calendar(self):
        """release_watch.yml の起動時刻は予定表から作ったものと同じ（予定を足したら sync-workflow を忘れない）"""
        cal = rw.load_calendar()
        self.assertEqual(rw.workflow_crons(), rw.crons(cal))
        ids = [e["id"] for e in cal["events"]]
        self.assertEqual(len(ids), len(set(ids)))
        for event in cal["events"]:
            start, end = rw.window(event)
            self.assertLess(start, end, event["id"])
            self.assertLessEqual(end - start, timedelta(hours=5, minutes=50), f"{event['id']}: ジョブの上限（6時間）に収まる")
            if event["kind"] == "pdf":
                for key in ("url", "period_re", "require", "title", "source_name", "article"):
                    self.assertTrue(event.get(key), f"{event['id']}: {key}")
                self.assertTrue(fast_lane.allowed_url(event.get("dispatch_url") or event["url"]), event["id"])
                self.assertTrue(event["article"].get("basis") and event["article"].get("figures"), event["id"])
        # 明日（11/6 08:30）の毎月勤労統計: 08:27〜09:05 を見張り、その前に4回起動する
        m = maikin_event()
        self.assertEqual(rw.window(m)[0].strftime("%m-%d %H:%M"), "11-06 08:27")
        self.assertIn("2 23 5 11 *", rw.crons(cal))
        self.assertTrue(m["url"].endswith("/r08/2609p/dl/houdou2609p.pdf"))

    def test_disabled_event_is_not_watched(self):
        cal = rw.load_calendar()
        boeki = next(e for e in cal["events"] if e["id"] == "boeki-2026-10")
        self.assertFalse(rw.enabled(boeki))
        now = rw.window(boeki)[0]
        self.assertNotIn("boeki-2026-10", [e["id"] for e in rw.active_events(cal, now)])


class FakePdf:
    """fetch と pdf_text.extract の差し替え（URL ごとの状態と中身）"""

    def __init__(self, status=404, text=""):
        self.status, self.text = status, text

    def fetch(self, url, timeout=20):
        return self.status, (b"%PDF-1.7 fake" if self.status == 200 else b"")

    def extract(self, data, **_):
        if self.text is None:
            raise pdf_text.PdfTextError("壊れている")
        return self.text


class DetectionTest(unittest.TestCase):
    def read(self, fake):
        with patch.object(rw, "fetch", fake.fetch), patch.object(rw.pdf_text, "extract", fake.extract):
            return rw.read_pdf_release(maikin_event())

    def test_unreadable_or_old_release_is_never_dispatched(self):
        event = maikin_event()
        # 404 → まだ / 前の月のまま → まだ / 壊れた PDF・数字の行が無い → 読めない（速報にしない）
        with self.assertRaises(rw.NotYet):
            self.read(FakePdf(404))
        with self.assertRaises(rw.NotYet):
            self.read(FakePdf(200, MAIKIN.replace("年9月分", "年8月分")))
        with self.assertRaises(rw.Unreadable):
            self.read(FakePdf(200, None))
        with self.assertRaises(rw.Unreadable):
            self.read(FakePdf(200, MAIKIN.replace("426,337 円(2.9%増)", "")))
        self.assertIn("426,337 円", self.read(FakePdf(200, MAIKIN)))

        cal = rw.load_calendar()
        start, end = rw.window(event)
        clock = {"now": start + timedelta(minutes=1)}

        def sleep(_):
            clock["now"] += timedelta(minutes=10)

        sent = []
        for fake, expected_rc, expected_sent in ((FakePdf(200, None), 1, 0), (FakePdf(404), 1, 0), (FakePdf(200, MAIKIN), 0, 1)):
            clock["now"] = start + timedelta(minutes=1)
            sent.clear()
            with patch.object(rw, "fetch", fake.fetch), patch.object(rw.pdf_text, "extract", fake.extract):
                rc = rw.run(cal, only=event["id"], now_fn=lambda: clock["now"], sleep=sleep, log=lambda *_: None,
                            deliver=lambda meta: sent.append(meta) or True)
            self.assertEqual((rc, len(sent)), (expected_rc, expected_sent))
        meta = sent[0]
        self.assertEqual(meta["url"], event["url"])
        self.assertIn("426,337 円", meta["text"])
        self.assertEqual(meta["release"]["basis"], "前年同月比")
        self.assertTrue(meta["release"]["preliminary"])
        self.assertEqual(meta["release"]["hosts"], ["www.mhlw.go.jp"])
        self.assertEqual(fast_lane.parse_meta(json.dumps(meta, ensure_ascii=False))[0]["title"], event["title"])

    def test_broken_pdf_text_is_rejected(self):
        self.assertFalse(pdf_text.looks_clean("\x00\x01ÿþ" * 200))
        self.assertFalse(pdf_text.looks_clean("短い"))
        self.assertTrue(pdf_text.looks_clean(MAIKIN))
        with self.assertRaises(pdf_text.PdfTextError):
            pdf_text.extract(b"<html>not a pdf</html>")

    def test_tdnet_hits_only_listed_companies_main_earnings_report(self):
        cal = rw.load_calendar()
        event = next(e for e in cal["events"] if e["id"] == "tdnet-2026-11-10")
        rows = [
            {"time": "15:30", "code": "72670", "company": "ホンダ", "title": "2027年3月期 第2四半期（中間期）決算短信〔IFRS〕（連結）", "url": "u1"},
            {"time": "15:30", "code": "72670", "company": "ホンダ", "title": "2027年3月期 第2四半期 決算補足説明資料", "url": "u2"},
            {"time": "15:30", "code": "72030", "company": "トヨタ", "title": "決算短信", "url": "u3"},
        ]
        self.assertEqual([h["url"] for h in rw.tdnet_hits(cal, event, rows)], ["u1"])


class DispatchTest(unittest.TestCase):
    def test_redispatches_when_pushed_out_and_never_doubles(self):
        meta = {"url": "https://www.mhlw.go.jp/x.pdf"}
        seq = [[], [{"databaseId": 1, "status": "queued"}], [{"databaseId": 1, "status": "completed", "conclusion": "cancelled"}],
               [{"databaseId": 1, "status": "completed", "conclusion": "cancelled"}, {"databaseId": 2, "status": "in_progress"}]]
        calls = []
        with patch.object(rw, "fast_runs", side_effect=lambda url: seq.pop(0) if len(seq) > 1 else seq[0]), \
                patch.object(rw, "dispatch", side_effect=lambda m: calls.append(m)):
            self.assertTrue(rw.ensure_fast_run(meta, log=lambda *_: None, sleep=lambda _: None))
        self.assertEqual(len(calls), 2)  # 最初の1回＋取り消された後の1回
        # 既に動いている実行があれば起こさない
        calls.clear()
        with patch.object(rw, "fast_runs", return_value=[{"databaseId": 3, "status": "in_progress"}]), \
                patch.object(rw, "dispatch", side_effect=lambda m: calls.append(m)):
            self.assertTrue(rw.ensure_fast_run(meta, log=lambda *_: None, sleep=lambda _: None))
        self.assertEqual(calls, [])


INFO = {"basis": "前年同月比", "preliminary": True, "hosts": ["www.mhlw.go.jp"], "name": "毎月勤労統計調査", "publisher": "厚生労働省",
        "figures": ["実質賃金", "名目賃金", "夏季賞与"], "leadRule": "実質賃金から書く", "notes": ""}
GOOD = {
    "scheduledRelease": INFO, "sourceUrl": "https://www.mhlw.go.jp/toukei/x.pdf",
    "title": "9月の実質賃金は前年同月比1.4%減、9か月連続のマイナス 夏の賞与は約43万円",
    "lede": "厚生労働省が6日発表した9月の毎月勤労統計調査（速報）で、実質賃金は前年同月比1.4%減でした。名目の現金給与総額は29万7,145円（1.9%増）です。",
    "highlights": ["夏季賞与の一人平均は42万6,337円で2.9%増"], "body": "本文", "easy": "",
}


class GateTest(unittest.TestCase):
    def test_numbers_units_direction_basis_and_forecasts_are_checked(self):
        self.assertEqual(release_quality.release_problems(GOOD, MAIKIN), [])
        cases = {
            "資料に無い": {"title": "9月の実質賃金は前年同月比1.5%減（速報）"},
            "向きが資料と逆": {"title": "9月の実質賃金は前年同月比1.4%増（速報）"},
            "比べる基準": {"title": "9月の実質賃金は1.4%減（速報）", "lede": "実質賃金は1.4%減でした（速報）。"},
            "「速報」と書かれていない": {"title": "9月の実質賃金は前年同月比1.4%減", "lede": "実質賃金は前年同月比1.4%減でした。"},
            "予想・見通し": {"title": "実質賃金は前年同月比1.4%減（速報）、年内にプラス転換の見通し"},
            "空欄の印": {"lede": "実質賃金は前年同月比〇〇%減でした（速報）。"},
            "単位": {"highlights": ["夏季賞与は2.9円増"]},
            "丸め": {"highlights": ["夏季賞与は約45万円"]},
            "出典": {"sourceUrl": "https://www.nikkei.com/article/x"},
        }
        for word, change in cases.items():
            problems = release_quality.release_problems({**GOOD, **change}, MAIKIN)
            self.assertTrue(any(word in p or (word == "単位" and "資料に無い" in p) or (word == "丸め" and "資料に無い" in p) for p in problems),
                            f"{word}: {problems}")
        # 予定表の速報でない記事には何もしない
        self.assertEqual(release_quality.release_problems({k: v for k, v in GOOD.items() if k != "scheduledRelease"}, ""), [])
        self.assertTrue(release_quality.release_problems(GOOD, ""))  # 資料が空なら確かめられない＝不合格

    def test_prompt_note_comes_from_the_calendar_not_a_fixed_text(self):
        note = release_quality.prompt_note(INFO)
        self.assertIn("前年同月比", note)
        self.assertIn("速報", note)
        self.assertIn("1. 実質賃金", note)
        self.assertEqual(release_quality.prompt_note({}), "")

    def test_every_writer_path_runs_the_release_gate(self):
        """公開前の門（quality.structural_problems）が予定表の速報の数字を確かめ、お知らせの門（A26）では止めない"""
        bad = {**GOOD, "sourceType": "web", "title": "9月の実質賃金は前年同月比1.5%減（速報）"}
        problems = quality.structural_problems(bad, "web", MAIKIN)
        self.assertTrue(any("公式の資料に無い" in p for p in problems), problems)
        stat_title = {"title": "企業物価指数（2026年10月速報）", "channelSlug": ""}
        self.assertIsNotNone(notice_gate.notice_reason(stat_title))
        self.assertIsNone(notice_gate.notice_reason({**stat_title, "scheduledRelease": INFO}))
        src = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn("release_quality.prompt_note(item[\"release\"])", src)
        self.assertIn('rec["scheduledRelease"] = item["release"]', src)


if __name__ == "__main__":
    unittest.main()


def test_scheduled_release_needs_no_japan_value_section():
    """日本の会社の決算・国の統計（scheduledRelease）は「日本で使える？」の章が無くても no-japan-value にしない（W35）"""
    import indexnow
    body = "## 中間期の業績\n" + "トヨタの営業収益は26兆9,624億円で前年同期比9.5%増えました。" * 120
    base = {"title": "トヨタ、中間期は増収増益", "genreSlug": "ai", "tags": ["決算"], "body": body, "slug": "toyota-x"}
    assert indexnow.noindex_reason({**base, "scheduledRelease": {"id": "tdnet"}}) != "no-japan-value"
    assert indexnow.noindex_reason(base) == "no-japan-value"
