"""広告通信なし。検索HTMLの形式変更と失敗時の候補・確認日保持を検証する。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rakuten_books as books


def card(rb="18420245", item="21778886", title="AI 議事録の仕事術", *, modern=True, stock=True):
    # 2026-10-30の公式HTMLで確認: classの追加、価格のspan入れ子、別要素のdata-item-id。
    extra = " notranslate-otft" if modern else ""
    price = '<span>2,200</span><span class="translate-otft">円</span>' if modern else "2,200円"
    return f"""<div data-ratunit='true' class='extra rbcomp__item-list__item'>
      <a href='https://books.rakuten.co.jp/rb/{rb}/?l-id=search-c-item-img-01'>
        <img alt='cover' src='https://tshop.r10s.jp/book/cabinet/2413/9784534062413_1_2.jpg?downsize=130:*' />
      </a>
      <h3><span class='rbcomp__category book'>本</span>
        <span class='rbcomp__item-list__item__title{extra}'>{title}</span></h3>
      <p class='rbcomp__item-list__item__author{extra}'><a>著者 &amp; 編集者</a></p>
      <p class='rbcomp__item-list__item__subtext{extra}'>2026年01月09日頃発売 ／ 出版社</p>
      <span class='rbcomp__item-list__item__price{extra}'><em>{price}</em></span>
      <div data-item-id='{item}' data-component='bdg-point-display'></div>
      <div class='rbcomp__item-list__item__review'><span></span><em>3.93</em><a>レビュー17件</a></div>
      <p class='rbcomp__item-list__item__stock'><i class='icon-record {'stock1' if stock else 'stock3'}'></i></p>
    </div>"""


class RakutenBooksTest(unittest.TestCase):
    old_date = "2026-10-28T23:45:38+00:00"
    new_date = "2026-10-30T06:00:00+00:00"

    def previous(self):
        return {"fetchedAt": self.old_date, "pixel": books.PIXEL,
                "books": {"voice": [{"rbId": "100", "title": "以前の本", "price": 1800, "url": "unchanged-ad-url"}],
                          "local": [{"rbId": "200", "title": "以前のPC本", "price": 2000}]},
                "partnerPrices": {"device": 30000}}

    def offers(self, topics=None, partners=None):
        return {"topics": topics or [{"key": "voice", "search": ["議事録"], "require": "議事録"}],
                "partners": partners or {}}

    def refresh(self, offers, previous=None, fetcher=None, prices=None):
        return books.refresh_catalog(offers, self.previous() if previous is None else previous, self.new_date,
                                     fetcher=fetcher or (lambda _: card()),
                                     price_fetcher=prices or (lambda _: 29000), sleeper=lambda _: None)

    def test_modern_class_and_nested_price_keep_ids_and_correct_values(self):
        row = books.parse(card())[0]
        self.assertEqual((row["rbId"], row["itemId"], row["price"], row["year"]), ("18420245", "21778886", 2200, 2026))
        self.assertEqual(row["author"], "著者 & 編集者")
        self.assertEqual((row["rating"], row["reviews"]), (3.93, 17))
        self.assertEqual(row["image"], "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/2413/9784534062413_1_2.jpg?_ex=400x400")

    def test_legacy_markup_still_works(self):
        self.assertEqual(books.parse(card(modern=False))[0]["price"], 2200)

    def test_out_of_stock_and_ebook_do_not_enter_books(self):
        page = card(stock=False) + card(rb="2", item="22").replace("rbcomp__category book", "rbcomp__category ebook")
        self.assertEqual(books.parse(page), [])

    def test_missing_release_date_is_not_guessed_or_selected(self):
        rows = books.parse(card().replace("2026年01月09日頃発売", "発売日未定"))
        self.assertEqual(rows[0]["year"], 0)
        self.assertEqual(books.pick(rows, set(), "", ""), [])

    def test_added_classes_do_not_join_two_cards_or_change_order(self):
        rows = books.parse(card() + card(rb="2", item="22", title="次の本"))
        self.assertEqual([(x["rbId"], x["rank"]) for x in rows], [("18420245", 1), ("2", 2)])

    def test_bad_response_and_partial_schema_loss_are_not_empty_success(self):
        for page in ["<html>Temporarily unavailable</html>", card() + card(rb="2", item="22").replace("data-item-id", "changed-id")]:
            with self.subTest(page=page[:30]):
                with self.assertRaises(books.ProductParseError):
                    books.parse(page)

    def test_existing_affiliate_url_and_pixel_format_are_unchanged(self):
        expected = "https://rpx.a8.net/svt/ejp?a8mat=4BELTP+50ED2Q+2HOM+BWGDT&rakuten=y&a8ejpredirect=https%3A%2F%2Fhb.afl.rakuten.co.jp%2Fhgc%2Fg00q0724.2bo11c45.g00q0724.2bo12179%2Fa26102173090_4BELTP_50ED2Q_2HOM_BWGDT%3Fpc%3Dhttps%253A%252F%252Fitem.rakuten.co.jp%252Fbook%252F18420245%252F%26m%3Dhttp%253A%252F%252Fm.rakuten.co.jp%252Fbook%252Fi%252F21778886%252F"
        self.assertEqual(books.affiliate_url("18420245", "21778886"), expected)
        self.assertEqual(books.PIXEL, "https://www15.a8.net/0.gif?a8mat=4BELTP+50ED2Q+2HOM+BWGDT")

    def test_total_failure_preserves_exact_previous_snapshot(self):
        before = self.previous()
        output, report = self.refresh(self.offers(), before, fetcher=lambda _: "<html>error</html>")
        self.assertEqual(output, before)
        self.assertEqual(report["outcome"], "failed")
        self.assertTrue(any(e["type"] == "ProductParseError" for e in report["errors"]))

    def test_partial_failure_retains_entire_snapshot_including_good_topic(self):
        offers = self.offers(topics=[{"key": "voice", "search": ["ok"]}, {"key": "local", "search": ["bad"]}])
        before = self.previous(); untouched = copy.deepcopy(before)
        output, report = self.refresh(offers, before, fetcher=lambda q: card() if q == "ok" else "blocked")
        self.assertEqual(report["outcome"], "partial")
        self.assertEqual(output, before)
        self.assertIn("voice", report["validatedTopics"])
        self.assertEqual(before, untouched)

    def test_failed_second_query_retains_whole_topic(self):
        offers = self.offers(topics=[{"key": "voice", "search": ["ok", "bad"]}])
        output, report = self.refresh(offers, fetcher=lambda q: card() if q == "ok" else "blocked")
        self.assertEqual(output, self.previous())
        self.assertEqual(report["retainedTopics"], ["voice"])

    def test_no_matching_books_does_not_erase_previous_topic(self):
        output, report = self.refresh(self.offers(), fetcher=lambda _: card(title="無関係な本"))
        self.assertEqual(output, self.previous())
        self.assertTrue(any(e["type"] == "NoMatchingBooks" for e in report["errors"]))

    def test_partner_failure_does_not_relabel_previous_price_as_fresh(self):
        output, report = self.refresh(self.offers(partners={"device": {"source": "plaud:example"}}), prices=lambda _: None)
        self.assertEqual(report["outcome"], "partial")
        self.assertEqual(output, self.previous())

    def test_complete_refresh_advances_date_and_preserves_url_contract(self):
        output, report = self.refresh(self.offers(partners={"device": {"source": "plaud:example"}}), previous={})
        self.assertEqual(report["outcome"], "success")
        self.assertEqual(output["fetchedAt"], self.new_date)
        self.assertEqual(output["partnerPrices"]["device"], 29000)
        self.assertEqual(output["books"]["voice"][0]["url"], books.affiliate_url("18420245", "21778886"))

    def test_dry_and_failed_main_never_write_products(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); products = root / "products.json"; offers = root / "offers.json"
            products.write_text(json.dumps(self.previous())); offers.write_text(json.dumps(self.offers()))
            original = products.read_bytes()
            for dry, outcome in [(True, "success"), (False, "failed"), (False, "partial")]:
                with self.subTest(dry=dry), patch.object(books, "PRODUCTS", products), patch.object(books, "OFFERS", offers), patch.object(books, "refresh_catalog", return_value=({"changed": True}, {"outcome": outcome})), patch.object(sys, "argv", ["rakuten_books.py"] + (["--dry"] if dry else [])):
                    books.main()
                    self.assertEqual(products.read_bytes(), original)

    def test_partial_main_preserves_requested_output_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); products = root / "products.json"; offers = root / "offers.json"
            output = root / "preview.json"; report = root / "report.json"
            products.write_text(json.dumps(self.previous())); offers.write_text(json.dumps(self.offers()))
            original = products.read_bytes()
            output.write_text("previous verified work snapshot")
            partial = {"fetchedAt": self.old_date, "books": {"voice": [{"price": 2200}]}}
            args = ["rakuten_books.py", "--output", str(output), "--report", str(report)]
            with patch.object(books, "PRODUCTS", products), patch.object(books, "OFFERS", offers), patch.object(books, "refresh_catalog", return_value=(partial, {"outcome": "partial"})), patch.object(sys, "argv", args):
                self.assertEqual(books.main(), 1)
            self.assertEqual(products.read_bytes(), original)
            self.assertEqual(output.read_text(), "previous verified work snapshot")
            self.assertEqual(json.loads(report.read_text())["outcome"], "partial")


if __name__ == "__main__":
    unittest.main()
