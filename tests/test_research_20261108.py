"""2026-11-08 オーナー決定（台帳 A64）: 写し書きにせず、公式・確かなページを下調べして価値を足す。
束の数字は確かめた数字。確かめた数字どうしの簡単な計算は「計算」と書けば使ってよい。Muse の出典も束に入れる。"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import calc_facts as cf  # noqa: E402
import facts_bundle as fb  # noqa: E402
import quality  # noqa: E402
import research  # noqa: E402

NOW = datetime(2026, 11, 8, 3, 0, tzinfo=timezone.utc)
HELP_TEXT = "\n".join([
    "ドコモからのお知らせが本物か確認する方法",
    "ドコモでは、主に以下の送信元からお客さまにご連絡をしています。",
    "判断がつかない場合、本文内のURLにはアクセスせず、公式アプリから確認してください。",
    "dアカウントのパスワードを変更する手順は、My docomo の設定から行えます。",
    "対象のお客さまには順次ご連絡します。不審なSMSにはご注意ください。",
])


class ArithmeticTest(unittest.TestCase):
    def test_labelled_calculation_is_allowed(self):
        text = "夫婦2人なら、1人50万円×2人＝100万円が上限です（サイソク編集部の計算）。"
        q = next(x for x in cf.extract(text) if x.value == 1_000_000)
        self.assertTrue(cf.derived(q, [500000.0], text))

    def test_monthly_total(self):
        text = "月額1,200円を12か月払うと年1万4,400円になる計算です。"
        q = next(x for x in cf.extract(text) if x.value == 14400)
        self.assertTrue(cf.derived(q, [1200.0], text))

    def test_unlabelled_or_unverified_is_not_allowed(self):
        text = "夫婦2人なら、1人50万円×2人で100万円が上限です。"
        q = next(x for x in cf.extract(text) if x.value == 1_000_000)
        self.assertFalse(cf.derived(q, [500000.0], text))  # 「計算」と書いていない
        text2 = "1人50万円×2人＝100万円（サイソク編集部の計算）。"
        q2 = next(x for x in cf.extract(text2) if x.value == 1_000_000)
        self.assertFalse(cf.derived(q2, [300000.0], text2))  # 材料の 50万円 が確かめた数字でない

    def test_wrong_expression_is_found(self):
        self.assertEqual(cf.bad_expressions("月額1,200円×12か月＝1万5,000円の計算"), ["1,200円×12か月=1万5,000円"])
        self.assertEqual(cf.bad_expressions("1人50万円×2人＝100万円"), [])

    def test_number_gate(self):
        source = "支援金は1人50万円です。"
        ok = {"title": "支援金の上限", "body": "夫婦2人なら1人50万円×2人＝100万円です（サイソク編集部の計算）。"}
        self.assertEqual(quality.number_problems(ok, source), [])
        bad = {"title": "支援金の上限", "body": "夫婦2人なら1人50万円×2人＝120万円です（サイソク編集部の計算）。"}
        self.assertTrue(quality.number_problems(bad, source))


class ResearchTest(unittest.TestCase):
    def _run(self, hits, pages, item=None, text="ドコモは11月8日、顧客情報の流出を発表した。"):
        item = item or {"title": "ドコモ、顧客情報の流出 対象者に連絡", "url": "https://www.docomo.ne.jp/info/news/x.html", "source_name": "NTTドコモ"}

        def fetcher(url, timeout):
            if url not in pages:
                raise OSError("404")
            return {"text": pages[url], "title": "", "final_url": url}

        return research.research(item, text, {"text": text, "links": []}, searcher=lambda q: hits, fetcher=fetcher, now=NOW)

    def test_reads_official_pages_only(self):
        hits = ["https://detail.chiebukuro.yahoo.co.jp/qa/1", "https://www.nikkei.com/article/x", "https://ameblo.jp/a/1",
                "https://www.docomo.ne.jp/info/anti-phishing/confirmation/", "https://www.soumu.go.jp/main_sosiki/x.html"]
        pages = {hits[3]: HELP_TEXT, hits[4]: HELP_TEXT.replace("ドコモ", "携帯電話会社のドコモ"), hits[1]: HELP_TEXT}
        got = self._run(hits, pages)
        urls = [g["url"] for g in got]
        self.assertIn(hits[3], urls)
        self.assertNotIn(hits[1], urls)  # 報道は読まない
        self.assertTrue(all(g["research"] for g in got))
        self.assertLessEqual(len(got), research.MAX_PAGES)

    def test_skips_the_same_press_release(self):
        url = "https://www.docomo.ne.jp/info/news/y.html"
        text = "\n".join(f"ドコモは本日、顧客情報の流出についての調査結果を公表しました。その{i}" + "あ" * 20 for i in range(6))
        got = self._run([url], {url: text}, text=text)
        self.assertEqual(got, [])

    def test_site_name_from_page_title(self):
        self.assertEqual(research.title_site("よくある質問：電子証明書｜マイナンバーカード総合サイト"), "マイナンバーカード総合サイト")
        self.assertEqual(research.site_label("https://www.example.co.jp/faq/", {}, "", "料金 | 例の会社"), "例の会社")

    def test_help_pages_rank_first(self):
        urls = ["https://www.docomo.ne.jp/news/2026/a.html", "https://www.docomo.ne.jp/support/faq/b.html"]
        self.assertEqual(research.rank(urls)[0], urls[1])

    def test_bundle_has_research_group_and_prompt(self):
        item = {"title": "ドコモ、顧客情報の流出 対象者に連絡", "url": "https://www.docomo.ne.jp/info/news/x.html", "source_name": "NTTドコモ"}
        url = "https://www.docomo.ne.jp/support/faq/b.html"
        bundle = fb.build(item, "ドコモは顧客情報の流出を発表した。", [], "public", {"text": "", "links": []},
                          fetcher=lambda u, t: {"text": HELP_TEXT, "title": "よくある質問"}, searcher=lambda q: [url], now=NOW)
        labels = [g.label for g in bundle.groups]
        self.assertIn("調べた公式情報", labels)
        block = bundle.prompt_block()
        self.assertIn("調べて足す価値", block)
        self.assertIn("サイソク編集部の計算", block)

    def test_no_search_without_page(self):
        item = {"title": "ドコモ、顧客情報の流出", "url": "https://www.docomo.ne.jp/x"}
        called = []
        fb.build(item, "本文", [], "public", None, searcher=lambda q: called.append(q) or [], now=NOW)
        self.assertEqual(called, [])


class MuseSourcesTest(unittest.TestCase):
    def test_muse_sources_go_into_bundle(self):
        sources = [{"url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1211-1.htm", "name": "国税庁",
                    "text": "住宅ローン控除の控除額は、年末の借入残高の0.7%です。\n" * 5, "facts": "0.7%"}]
        groups = fb.muse_groups(sources, "住宅ローン控除の限度額", NOW)
        self.assertEqual(groups[0].label, "Museの出典")
        self.assertIn("0.7%", groups[0].body)
        record = {"title": "住宅ローン控除", "body": "控除は年末残高の0.7%です（国税庁、11/8確認）。", "_facts": {"groups": [
            {"label": g.label, "name": g.name, "url": g.url, "checked": g.checked, "body": g.body, "marks": g.marks} for g in groups]}}
        self.assertEqual(quality.number_problems(record, "住宅ローン控除の発表。"), [])


if __name__ == "__main__":
    unittest.main()
