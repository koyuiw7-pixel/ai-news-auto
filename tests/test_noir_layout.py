"""新しい記事の見た目「ノワール」の印と要点の欄（scripts/noir_layout.py・台帳 W36）。

- 新しく書き出す記事だけに layout: "noir" を付ける（今ある記事のファイルは書き換えない）
- 欄の中身は、品質ゲートを通った本文・要点の文字をそのまま抜き出したものだけ（記事に無い数字は出さない・計算で数字を作らない）
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import main as m  # noqa: E402
import noir_layout  # noqa: E402

BODY = """## LUXIONは20万1,300円安く

LUXIONは装備が標準になり、価格は**税込479万7,100円**です。

| 比べること | これまで | 今回 | 変化 |
|---|---|---|---|
| LUXION 2WD e-POWER | 499万8,400円 | 479万7,100円 | **20万1,300円安く** |
| ホットプラスパッケージ | オプション | 標準 | 標準に |

## グレードごとに

| グレード | 内容 |
|---|---|
| LUXION | 20万1,300円の値下げ。寒さ対策の装備2つが標準に |
| ハイウェイスターV | 照らし方を変えるLEDヘッドライトが標準に |
"""


def record(**extra) -> dict:
    base = {
        "slug": "nissan-serena-luxion-price",
        "sourceType": "web",
        "title": "セレナ最上級「LUXION」、20万円安く",
        "lede": "日産はセレナの価格を改定しました。",
        "highlights": ["セレナの最上級「LUXION」が20万1,300円値下げ。寒い日の装備も標準になりました"],
        "body": BODY,
    }
    base.update(extra)
    return base


class DeriveTest(unittest.TestCase):
    def test_fields_come_from_the_gated_text(self):
        r = record()
        notes = noir_layout.attach(r)
        self.assertEqual(r["layout"], "noir")
        self.assertTrue(notes)
        self.assertEqual(r["changes"][0], {"label": "LUXION 2WD e-POWER", "before": "499万8,400円", "after": "479万7,100円", "note": "20万1,300円安く"})
        self.assertEqual(r["changes"][1]["after"], "標準")
        # 値は記事に書いてある文字のまま（「479.7万円」のような丸めた数字を作らない）
        self.assertEqual(r["keyFigure"], {"value": "479万7,100", "unit": "円", "label": "LUXION 2WD e-POWER", "before": "499万8,400円"})
        self.assertEqual(r["summaryLine"], "セレナの最上級「LUXION」が**20万1,300円**値下げ。寒い日の装備も標準になりました")
        self.assertEqual([w["name"] for w in r["wrapUp"]], ["LUXION", "ハイウェイスターV"])

    def test_number_not_in_article_drops_the_field(self):
        r = record()
        fields = noir_layout.derive(r)
        self.assertIn("keyFigure", fields)
        # 本文・要点・リードに無い数字が混ざった欄は出さない
        self.assertFalse(noir_layout._grounded({"value": "480", "unit": "万円"}, BODY))
        self.assertTrue(noir_layout._grounded({"value": "479万7,100", "unit": "円"}, BODY))

    def test_optional_when_article_has_no_tables(self):
        r = record(body="## 発表\n\n数字の無い本文です。", highlights=["新しい機能が出ました"])
        noir_layout.attach(r)
        self.assertEqual(r["layout"], "noir")
        self.assertEqual(r.get("summaryLine"), "新しい機能が出ました")
        for key in ("keyFigure", "changes", "wrapUp"):
            self.assertNotIn(key, r)

    def test_label_qualifiers_are_not_used_as_labels(self):
        fig = noir_layout.key_figure([], ["ドコモのタッチペンは税込1,200円です"])
        self.assertIsNone(fig)
        fig = noir_layout.key_figure([], ["KDDIの上期決算、売上高3兆528億円で前年同期比4.7%増"])
        self.assertEqual(fig, {"value": "3兆528億", "unit": "円", "label": "売上高"})

    def test_video_and_roundup_keep_the_old_look(self):
        for r in (record(sourceType="youtube"), record(type="roundup")):
            self.assertEqual(noir_layout.attach(r), [])
            self.assertNotIn("layout", r)


class HeroOkTest(unittest.TestCase):
    """ノワールの表紙に写真を出すのは、大きな文字の無い本物の写真だけ（迷ったら黒い表紙）"""

    def setUp(self):
        import images  # noqa: PLC0415

        self.images = images
        self.photo = images.Image.new("RGB", (1200, 675), (40, 90, 140))

    def fake(self, *answers):
        replies = list(answers)
        return lambda image, prompt, max_tokens=0: replies.pop(0) if replies else None

    def test_real_photo_passes(self):
        ok, _ = self.images.hero_ok(self.photo, "photo", "https://example.com/news/serena.jpg", vision=self.fake("photo", "no"))
        self.assertTrue(ok)

    def test_banner_slide_and_unknown_fail(self):
        h = self.images.hero_ok
        self.assertFalse(h(self.photo, "banner", "https://x/a.jpg", vision=self.fake("photo", "no"))[0])
        self.assertFalse(h(self.photo, "hero", "https://x/a.jpg", vision=self.fake("photo", "no"))[0])
        self.assertFalse(h(self.photo, "photo", "https://x/uploads/OGP-scaled.png", vision=self.fake("photo", "no"))[0])
        self.assertFalse(h(self.photo, "photo", "https://x/a.jpg", vision=self.fake("text-heavy"))[0])
        self.assertFalse(h(self.photo, "photo", "https://x/a.jpg", vision=self.fake("photo", "yes"))[0])
        self.assertFalse(h(self.photo, "photo", "https://x/a.jpg", vision=self.fake())[0])  # 判定できない
        tall = self.images.Image.new("RGB", (800, 1200))
        self.assertFalse(h(tall, "photo", "https://x/a.jpg", vision=self.fake("photo", "no"))[0])

    def test_images_decides_for_noir_articles(self):
        src = (Path(__file__).resolve().parent.parent / "scripts" / "images.py").read_text("utf-8")
        self.assertIn('if article.get("layout") == "noir":', src)
        self.assertIn('article["heroOk"] = ok', src)


class WriteArticleTest(unittest.TestCase):
    def test_only_new_files_get_the_new_look(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(m, "ARTICLES_DIR", Path(tmp)), \
                    mock.patch.object(m.headline_normalize, "apply", return_value=[]), \
                    mock.patch.object(m.headline_normalize, "title_problems", return_value=[]), \
                    mock.patch.object(m.section_gate, "apply", return_value=[]), \
                    mock.patch.object(m.article_style, "autofix", return_value=[]), \
                    mock.patch.object(m.public_interest, "autofix", return_value=[]):
                path = m.write_article(record())
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["layout"], "noir")
                # 今ある記事を書き直す経路では、印を付けない（今までの見た目のまま）
                old = record(slug="old-article")
                (Path(tmp) / "old-article.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
                path = m.write_article(dict(old))
                self.assertNotIn("layout", json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
