"""2026-11-17: 厚生労働省の食品リコール（i2fas 公開回収事案詳細）の本文が読めず、Muse の回収記事が
「出典（公式ページ）を1本も読めませんでした」で10本以上落ちた。

原因: 本文の表がまるごと <form> の中にあり、feeds._Extractor が form を読み飛ばしていた（37字しか残らない）。
直し: 本文がほとんど取れず <form> があるページだけ、form の中も読み直す。そのとき display:none で隠した要素
（i2fas は「指定された公開回収事案は、削除されています。」を隠して置いている）は読まない。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import feeds  # noqa: E402

ROWS = "".join(
    f'<div class="row"><div class="label">{k}</div><div class="value"><span>{v}</span></div></div>'
    for k, v in [
        ("整理番号", "RCL202602932"),
        ("届出年月日", "2026-11-16"),
        ("公開年月日", "2026-11-16"),
        ("届出者名", "株式会社いちい"),
        ("商品名", "しらす干し"),
        ("食品等の特定情報", "形態：パック包装 内容量：１００～４００ｇ 消費期限：26年11月17日"),
        ("回収の理由", "食品衛生法違反のおそれ"),
        ("詳細", "ふぐの稚魚と疑われる魚種の混入があったため 食品衛生法第20条に該当"),
        ("販売状況", "当該店舗において、11月13日に15パック、11月14日に17パック販売"),
        ("回収方法", "【周知方法】 店頭でのＰＯＰ掲示 【問合せ先】 024-563-1148 【回収後の対応】 返金対応"),
        ("回収状況", "11月16日時点で400g 1パック回収済み（１/32パック） 11月17日回収終了予定"),
        ("健康被害の発生状況", "無 詳細 健康被害の発生はなし"),
        ("健康への危険性の程度", "CLASSⅠ"),
    ]
)

I2FAS_PAGE = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>食品衛生公開[公開回収事案詳細]</title></head><body>
<div class="loading"><div class="loading-text">送信中です</div><div class="loading-text">受信中です</div></div>
<header><a href="#main">本文へ</a><ul><li>よくあるご質問（FAQ）</li></ul></header>
<form id="form" name="IoIO_S020502Form" action="/faspub/IO_S020502.do" method="POST">
<h1>公開回収事案詳細</h1>
<p>公開されている食品リコール情報を参照します。</p>
<div id="_f_err_mag_str_item" style="display: none;">
<input type="hidden" name="_f_err_mag_str" value="x"/><span>指定された公開回収事案は、削除されています。</span>
</div>
<div hidden><span>隠した案内</span></div>
{ROWS}
</form>
<footer>Copyright © Ministry of Health, Labour and Welfare</footer>
</body></html>""".encode()

URL = "https://i2fas.mhlw.go.jp/faspub/_link.do?i=IO_S020502&p=RCL202602932"


def _direct(body: bytes) -> dict:
    with patch.object(feeds, "_fetch_cached", return_value=(body, URL)):
        return feeds._fetch_direct(URL)


class RecallFormPageTest(unittest.TestCase):
    def test_reads_recall_table_inside_form(self):
        text = _direct(I2FAS_PAGE)["text"]
        self.assertGreaterEqual(len(text), 300, text)
        for want in ("しらす干し", "ふぐの稚魚", "024-563-1148", "返金対応", "CLASSⅠ", "消費期限：26年11月17日"):
            self.assertIn(want, text)

    def test_hidden_error_message_is_not_read(self):
        # 隠された「削除されています」を本文に入れると、記者が回収の終わった話と取り違える
        text = _direct(I2FAS_PAGE)["text"]
        self.assertNotIn("削除されています", text)
        self.assertNotIn("隠した案内", text)
        self.assertNotIn("Copyright", text)  # footer は今までどおり読まない

    def test_reads_full_page_through_fetch_article_text(self):
        feeds._article_memo.pop(URL, None)
        with patch.object(feeds, "_fetch_cached", return_value=(I2FAS_PAGE, URL)), \
             patch.object(feeds, "_fetch_via_reader", side_effect=AssertionError("読み取りサービスは不要")), \
             patch.object(feeds, "_fetch_via_api", side_effect=AssertionError("API は不要")):
            page = feeds.fetch_article_text(URL)
        feeds._article_memo.pop(URL, None)
        self.assertIn("ふぐの稚魚", page["text"])

    def test_normal_page_still_skips_forms(self):
        # 本文が十分に取れるページでは、今までどおり form（検索窓・問い合わせ欄）は読まない
        body = ("<html><body><article><h1>お知らせ</h1>" + "<p>" + "本文の段落です。" * 80 + "</p></article>"
                "<form><label>検索フォームの文言</label></form></body></html>").encode()
        text = _direct(body)["text"]
        self.assertIn("本文の段落です。", text)
        self.assertNotIn("検索フォームの文言", text)

    def test_page_without_form_unchanged(self):
        body = b"<html><body><div style='display:none'>hidden-but-legacy</div><p>short</p></body></html>"
        text = _direct(body)["text"]
        # form の無いページは今までの読み方のまま（display:none も読む = 変更なし）
        self.assertIn("hidden-but-legacy", text)


if __name__ == "__main__":
    unittest.main()
