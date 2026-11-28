"""2026-11-28: 消費者庁 リコール情報サイトの新着（食品の回収も）を軸の候補にする（scripts/caa_recall.py）と、
話題のレーンで暮らし・お金・安全の言葉を先に回す（scripts/trend_lane.py の axis_rank / axis_order）。外部への通信なし。

- 厚生労働省の i2fas は robots.txt が /faspub/ を禁止しているので読まない。消費者庁のサイトの詳しいページは本文が Quill の
  script の中にある（feeds.expand_quill で読み出す）
- 詳しいページの URL はクエリ（rcl=…）で1件が決まる。クエリを落とすと全部「同じ出典URL」になっていた（dedupe.KEEP_QUERY）
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import caa_recall  # noqa: E402
import dedupe  # noqa: E402
import feeds  # noqa: E402
import public_interest  # noqa: E402
import trend_lane  # noqa: E402
import your_number  # noqa: E402

JST = timezone(timedelta(hours=9))


def quill(span_id: str, text: str) -> str:
    ops = json.dumps({"ops": [{"insert": text}]}, ensure_ascii=False)
    js = ops.replace("\\", "\\\\").replace('"', '\\"').replace("/", "\\/")
    return (f'<span class="detail_text quilltext" id="{span_id}"></span>\n<script type="text/javascript">\n<!--\n'
            f"contentsText = '{js}';\nquill = new Quill('#{span_id}', {{readOnly: true}});\nquill.setContents(JSON.parse(contentsText));\n-->\n</script>")


def detail_page(title: str, spec: str, contact: str = "テスト食品株式会社\n電話番号：0120-000-000\n受付時間：平日9:00～17:00",
                category: str = "食料品") -> str:
    return f"""<html><head><title>商品情報詳細｜リコール情報サイト｜消費者庁</title></head><body>
<ol><li><a href="/index.php?screenkbn=01">ホーム</a></li><li><a href="index.php?screenkbn=01&category=1" title="">{category}</a></li></ol>
<div class="detail_title">
<h3>{title}</h3>
<!-- 20190328 activet start -->
<p>アレルゲン（卵）の表示欠落</p>
</div>
<div class="detail_box_top clearfix"><div class="detail_box_left"><ul>
<li><span class="detail_cap">商品名</span><span class="detail_text">テストのクッキー</span></li>
<li class="new_window"><span class="detail_cap">連絡先</span>{quill("details1", contact)}</li>
<li class="new_window"><span class="detail_cap">対応方法</span>{quill("details2", "【回収方法】\n着払いで送付\n【回収後の対応】\n返金対応")}</li>
<li><span class="detail_cap">対応開始日</span><span class="detail_text">2026年11月24日</span></li>
</ul></div>
<div class="detail_box_right"><ul class="detail_main_img"><li><a href="/images/rci/img/product/00000036299_1.jpg">x</a></li></ul></div></div>
<div class="detail_box_bottom clearfix"><ul>
<li class="new_window"><span class="detail_cap">対象の特定情報</span>{quill("details3", spec)}</li>
<li class="new_window"><span class="detail_cap">参照情報</span><span class="detail_text">【厚生労働省】食品衛生等申請システム
<span class="detail_text_link"><a href="https://i2fas.mhlw.go.jp/faspub/_link.do?i=IO_S020502&p=RCL202609999" target="_blank">参照情報</a></span></span></li>
<li class="new_window"><span class="detail_cap" id="reason">備考</span>{quill("details4", "回収理由の詳細：\n卵の表示が欠落していました。")}</li>
</ul></div>
<div class="control_number">管理番号：00000036299</div></body></html>"""


WIDE_SPEC = "商品名：テストのクッキー\n内容量：120g\nJANコード：4900000000000\n賞味期限：2027年1月10日\n販売地域：全国\n販売数量：3,200個"
TINY_SPEC = "商品名：テストのクッキー\n内容量：120g\n消費期限：2026年11月20日\n販売先：当該店舗\n販売数量：40個"

LIST_PAGE = """<table><tbody>
<tr><td><span class="result_list_category category_1">食料品</span></td><td class="width60"><a href="/images/rci/img/product/00000036299_1.jpg"><img alt="x"></a></td>
<td class="new_window"><p><a href="/result/detail.php?rcl=00000036299&screenkbn=03" target="_blank">テスト食品「テストのクッキー」 - 返金／回収</a></p></td>
<td><span class="result_list_post_date">2026/11/26</span></td><td><span class="result_list_start_date">2026/11/24</span></td></tr>
<tr><td><span class="result_list_category category_8">車両・乗り物</span></td><td></td>
<td class="new_window"><p><a href="/result/detail.php?rcl=00000036205&screenkbn=03" target="_blank">乗用車（スバル フォレスター、ほか3車種） - 修理</a></p></td>
<td><span class="result_list_post_date">2026/11/26</span></td><td><span class="result_list_start_date">2026/11/26</span></td></tr>
</tbody></table>"""


class CaaRecallTest(unittest.TestCase):
    def setUp(self):
        caa_recall._session_state = None
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(caa_recall, "STATE_PATH", Path(self.tmp.name) / "caa_recall.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, caa_recall, "_session_state", None)

    def test_robots_disallowed_i2fas_is_not_a_feed(self):
        urls = [f["url"] for f in feeds.FEEDS + feeds.BROAD_FEEDS]
        self.assertFalse(any("i2fas.mhlw.go.jp" in u for u in urls))
        feed = feeds.FEEDS_BY_SLUG["caa-recall"]
        self.assertEqual(feed["type"], "caa_recall")
        self.assertEqual(feed["kind"], "gov")
        self.assertIn("recall.caa.go.jp", feed["url"])

    def test_list_rows(self):
        rows = caa_recall.parse_list(LIST_PAGE)
        self.assertEqual([r["rcl"] for r in rows], ["00000036299", "00000036205"])
        self.assertEqual(rows[0]["category"], "食料品")
        self.assertEqual(rows[0]["posted"], datetime(2026, 11, 26, tzinfo=JST))
        self.assertEqual(rows[0]["started"], datetime(2026, 11, 24, tzinfo=JST))

    def test_quill_text_is_read(self):
        page = detail_page("テスト食品「テストのクッキー」 - 返金／回収", WIDE_SPEC)
        rec = caa_recall.parse_detail(page, "00000036299")
        self.assertEqual(rec["category"], "食料品")
        self.assertEqual(rec["headline"], "アレルゲン（卵）の表示欠落")
        self.assertIn("0120-000-000", rec["contact"])
        self.assertIn("賞味期限：2027年1月10日", rec["spec"])
        self.assertIn("返金対応", rec["action"])
        self.assertEqual(rec["started"], "2026年11月24日")
        self.assertEqual(rec["referenceUrls"], ["https://i2fas.mhlw.go.jp/faspub/_link.do?i=IO_S020502&p=RCL202609999"])
        # 記事の本文を読む経路（feeds._fetch_direct）でも script の中の文字が本文に入る
        with patch.object(feeds, "_fetch_cached", return_value=(page.encode(), "https://www.recall.caa.go.jp/result/detail.php?rcl=00000036299")):
            text = feeds._fetch_direct("https://www.recall.caa.go.jp/result/detail.php?rcl=00000036299")["text"]
        self.assertIn("0120-000-000", text)
        self.assertIn("JANコード：4900000000000", text)

    def test_expand_quill_leaves_other_pages_alone(self):
        page = "<html><body><p>ふつうのページ</p><script>var a = 1;</script></body></html>"
        self.assertEqual(feeds.expand_quill(page), page)

    def test_significance(self):
        row = {"rcl": "1", "title": "", "category": "食料品"}
        wide = caa_recall.parse_detail(detail_page("テスト食品「テストのクッキー」 - 返金／回収", WIDE_SPEC), "1")
        self.assertTrue(caa_recall.significance(row, wide, [])[0])
        tiny = caa_recall.parse_detail(detail_page("テスト食品（駅前店）「テストのクッキー」 - 返金／回収", TINY_SPEC), "1")
        ok, why = caa_recall.significance(row, tiny, [])
        self.assertFalse(ok)
        self.assertIn("小さな範囲", why)
        b2b = caa_recall.parse_detail(detail_page("テスト食品「業務用 焼ちくわ（冷凍）60本バラ」 - 回収", "内容量：60本\n販売先：飲食店"), "1")
        self.assertEqual(caa_recall.significance(row, b2b, [])[1], "業務用（事業者向けの品）")
        car = {"title": "乗用車（スバル フォレスター、ほか3車種） - 修理", "category": "車両・乗り物"}
        self.assertFalse(caa_recall.significance(row, car, [])[0])
        toy = caa_recall.parse_detail(detail_page("テスト玩具「おもちゃ」 - 交換／返金", "品番：A-1", category="文具・娯楽用品"), "1")
        self.assertTrue(caa_recall.significance(row, toy, [])[0])
        major = caa_recall.parse_detail(detail_page("ヱスビー食品（明治）「ディナーカレーフレーク1kg」 - 返金／回収", "内容量：1kg"), "1")
        self.assertIn("全国で知られた名前", caa_recall.significance(row, major, ["明治"])[1])

    def test_item_is_on_axis_recall_with_your_number_elements(self):
        row = caa_recall.parse_list(LIST_PAGE)[0]
        rec = caa_recall.parse_detail(detail_page(row["title"], WIDE_SPEC), row["rcl"])
        item = caa_recall.build_item(row, rec, "テスト", feeds.FEEDS_BY_SLUG["caa-recall"])
        self.assertEqual(item["url"], "https://www.recall.caa.go.jp/result/detail.php?rcl=00000036299")
        self.assertEqual(public_interest.category(item["title"]), "recall")
        self.assertTrue(public_interest.is_candidate(item, "gov"))
        self.assertEqual(your_number.item_kind(item), "alert")
        self.assertEqual(item["_incident"]["kind"], "recall")
        text = item["content"]
        for want in ("賞味期限：2027年1月10日", "内容量：120g", "0120-000-000", "対応開始日: 2026年11月24日",
                     "回収・返金の受付の期限: 掲載内容には書かれていない", "RCL202609999", item["url"]):
            self.assertIn(want, text)
        self.assertGreaterEqual(len(text), 300)

    def test_candidates_skip_covered_and_remember(self):
        calls = []

        def get(url):
            calls.append(url)
            return LIST_PAGE if "index.php" in url else detail_page("テスト食品「テストのクッキー」 - 返金／回収", WIDE_SPEC)
        now = datetime(2026, 11, 27, 12, tzinfo=JST)
        with patch.object(caa_recall, "covered_ids", return_value=(set(), set())), \
                patch.object(caa_recall, "_recent_products", return_value=[]), patch.object(caa_recall, "FETCH_GAP_SEC", 0):
            items = caa_recall.candidates({"slug": "caa-recall", "name": "消費者庁", "url": caa_recall.LIST_URL}, now=now, get=get)
            self.assertEqual([i["caaRecall"]["rcl"] for i in items], ["00000036299"])  # 車は読まない
            self.assertEqual(sum(1 for c in calls if "detail.php" in c), 1)
            again = caa_recall.candidates({"slug": "caa-recall", "name": "消費者庁", "url": caa_recall.LIST_URL}, now=now, get=get)
            self.assertEqual(len(again), 1)
            self.assertEqual(sum(1 for c in calls if "detail.php" in c), 1, "記録した詳しいページは読み直さない")
        with patch.object(caa_recall, "covered_ids", return_value=({"00000036299"}, set())), patch.object(caa_recall, "_recent_products", return_value=[]):
            self.assertEqual(caa_recall.candidates({"url": caa_recall.LIST_URL}, now=now, get=get), [])
        with patch.object(caa_recall, "covered_ids", return_value=(set(), {"RCL202609999"})), patch.object(caa_recall, "_recent_products", return_value=[]):
            caa_recall._session_state = {"items": {}}
            self.assertEqual(caa_recall.candidates({"url": caa_recall.LIST_URL}, now=now, get=get), [], "同じ i2fas の届出の記事がある")

    def test_dedupe_keeps_identifying_query(self):
        index = dedupe.Index()
        index.add("A社「クッキー」のリコール（返金／回収）", "https://www.recall.caa.go.jp/result/detail.php?rcl=00000036201&screenkbn=06")
        self.assertTrue(index.has_url("https://www.recall.caa.go.jp/result/detail.php?rcl=00000036201"))
        self.assertFalse(index.has_url("https://www.recall.caa.go.jp/result/detail.php?rcl=00000036202"))
        self.assertEqual(dedupe._norm_url("https://example.com/a?utm_source=x"), "https://example.com/a")
        # 別の商品の回収どうしは「リコール・返金回収」の言葉だけでは重複にしない
        self.assertIsNone(index.find("B社「おせんべい」のリコール（返金／回収）"))


class TrendAxisTest(unittest.TestCase):
    def q(self, title, *titles, genre="public", traffic=100):
        return {"title": title, "genre": genre, "traffic": traffic, "sources": [{"title": t} for t in titles]}

    def test_axis_rank(self):
        self.assertEqual(trend_lane.axis_rank(self.q("低所得者", "高齢者が支払う介護保険料 年間所得が120万円以上で引き上げ案")), 0)
        self.assertEqual(trend_lane.axis_rank(self.q("ビックカメラ 情報流出", "個人情報漏洩の恐れ")), 0)
        self.assertEqual(trend_lane.axis_rank(self.q("ワクワク", "しまむら「ブラックフライデー」本日スタート。「96円」商品も")), 0)
        self.assertEqual(trend_lane.axis_rank(self.q("中川圭太", "阪神、FAの中川圭太と4年10億円超で契約合意")), 2)
        self.assertEqual(trend_lane.axis_rank(self.q("榊原 郁恵", "芸能生活50周年記念公演", genre="sports")), 2)
        self.assertEqual(trend_lane.axis_rank(self.q("辻希美", "5児の母・辻希美、長女との“顔出し”親子3ショット公開")), 2)
        self.assertEqual(trend_lane.axis_rank(self.q("横浜 天気", "横浜の過去の天気")), 1)
        # 言葉そのものが家計の語なら、スポーツの見出しが混ざっていても軸
        self.assertEqual(trend_lane.axis_rank(self.q("チケット 値上げ", "プロ野球の観戦チケットを値上げ", genre="sports")), 0)

    def test_axis_order_keeps_every_term(self):
        queue = [self.q("辻希美", "親子3ショット公開", traffic=5000), self.q("横浜 天気", "天気", traffic=2000),
                 self.q("年金", "年金の支給日", traffic=100), self.q("給付", "給付金の申請", traffic=500)]
        ordered = trend_lane.axis_order(queue)
        self.assertEqual([q["title"] for q in ordered], ["給付", "年金", "横浜 天気", "辻希美"])
        self.assertEqual(trend_lane.axis_counts(queue), {0: 2, 1: 1, 2: 1})


if __name__ == "__main__":
    unittest.main()
