"""A8 の取込（scripts/a8_import.py）を2回続けて実行しても何も変わらず、提携先の取りこぼしが無いことを確かめる（通信なし）。"""
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a8_import  # noqa: E402

# 取込の対象外と決めているもの（a8_import.py の説明に書いた理由のとおり）
EXCEPTIONS = {
    "s00000025808001",  # PLAUD: 商品ごとの枠
    "s00000027222001",  # OZ GAMING: 商品ごとの枠
    "s00000011623001",  # 楽天アフィリエイト: 商品ページへのリンクの仕組み
    "s00000008903009",  # TOSSY: オーナーの判断待ち
}
EXCEPTION_NAMES = ("PLAUD", "Plaud", "OZ GAMING", "楽天")

# 2026-11-10（M1 の前）の origin/main で使っていたリンクと計測ピクセル。取込でこの組を入れ替えない
LIVE = {
    "mf-setsuritsu": ("4BGCEZ+2T7PMA+4JGQ+HVFKY", "https://www15.a8.net/0.gif?a8mat=4BGCEZ+2T7PMA+4JGQ+HVFKY"),
    "yayoi-kaigyou": ("4BGCEY+GCTQ2A+35XE+HZPWI", "https://www16.a8.net/0.gif?a8mat=4BGCEY+GCTQ2A+35XE+HZPWI"),
    "yayoi-setsuritsu": ("4BGCEY+GCTQ2A+35XE+HXD0Y", "https://www16.a8.net/0.gif?a8mat=4BGCEY+GCTQ2A+35XE+HXD0Y"),
    "abema-premium": ("4BGCEZ+3PYJW2+4EKC+63OY9", "https://www15.a8.net/0.gif?a8mat=4BGCEZ+3PYJW2+4EKC+63OY9"),
    "conoha-ai-canvas": ("4BELTP+C1FL6A+50+7S2QE9", "https://www19.a8.net/0.gif?a8mat=4BELTP+C1FL6A+50+7S2QE9"),
}
# 本文中の文字リンク（affiliate_links.json）。枠とは別の素材のものもある
LIVE_TEXT_LINKS = {
    "ConoHa AI Canvas": ("4BELTP+C1FL6A+50+7RU5R6", "https://www18.a8.net/0.gif?a8mat=4BELTP+C1FL6A+50+7RU5R6"),
    "Value AI Writer": ("4BEO5P+CLOBQQ+1JUK+1HL85U", "https://www13.a8.net/0.gif?a8mat=4BEO5P+CLOBQQ+1JUK+1HL85U"),
    "弥生 起業・開業ナビ": ("4BGCEY+GCTQ2A+35XE+HZPWI", "https://www16.a8.net/0.gif?a8mat=4BGCEY+GCTQ2A+35XE+HZPWI"),
    "マネーフォワード クラウド会社設立": ("4BGCEZ+2T7PMA+4JGQ+HVFKY", "https://www15.a8.net/0.gif?a8mat=4BGCEZ+2T7PMA+4JGQ+HVFKY"),
    "ABEMAプレミアム": ("4BGCEZ+3PYJW2+4EKC+63OY9", "https://www15.a8.net/0.gif?a8mat=4BGCEZ+3PYJW2+4EKC+63OY9"),
}
A8 = "https://px.a8.net/svt/ejp?a8mat="


def run_importer(root: Path) -> None:
    tsv = ROOT / ".claude" / "a8_partnered.tsv"
    with patch.multiple(a8_import, TSV=tsv if tsv.exists() else root / "missing.tsv",
                        LINKS=root / "affiliate_links.json", OFFERS=root / "offers.json"), redirect_stdout(io.StringIO()):
        assert a8_import.main() == 0


class ImportIdempotentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy(ROOT / "content" / "offers.json", self.root / "offers.json")
        shutil.copy(ROOT / "affiliate_links.json", self.root / "affiliate_links.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_running_twice_changes_nothing(self):
        run_importer(self.root)
        first = [(self.root / n).read_bytes() for n in ("offers.json", "affiliate_links.json")]
        run_importer(self.root)
        second = [(self.root / n).read_bytes() for n in ("offers.json", "affiliate_links.json")]
        self.assertEqual(first, second)

    def test_committed_files_are_what_the_importer_writes(self):
        run_importer(self.root)
        self.assertEqual((self.root / "offers.json").read_bytes(), (ROOT / "content" / "offers.json").read_bytes())
        self.assertEqual((self.root / "affiliate_links.json").read_bytes(), (ROOT / "affiliate_links.json").read_bytes())

    def test_every_a8_partner_is_maintained_or_documented(self):
        keys = {meta["key"] for meta in a8_import.PARTNERS.values()}
        pids = {entry.split("#")[0] for entry in a8_import.PARTNERS}
        doc = a8_import.__doc__ or ""
        for pid in EXCEPTIONS:
            self.assertIn(pid, doc)
            self.assertNotIn(pid, pids)
        offers = json.loads((ROOT / "content" / "offers.json").read_text("utf-8"))["partners"]
        for key, partner in offers.items():
            if not (partner.get("programId") or str(partner.get("link", "")).startswith(A8)):
                continue
            with self.subTest(key=key):
                documented = partner.get("programId") in EXCEPTIONS or any(n in str(partner.get("program", "")) for n in EXCEPTION_NAMES)
                self.assertTrue(key in keys or documented, f"{key} は取込の対象外で、理由も書かれていない")

    def test_live_link_and_pixel_pairs_are_kept(self):
        run_importer(self.root)
        offers = json.loads((self.root / "offers.json").read_text("utf-8"))["partners"]
        links = json.loads((self.root / "affiliate_links.json").read_text("utf-8"))
        for key, (code, pixel) in LIVE.items():
            with self.subTest(key=key):
                self.assertEqual(offers[key]["link"], A8 + code)
                self.assertEqual(offers[key]["pixel"], pixel)
        self.assertEqual(offers["conoha-ai-canvas"]["image"],
                         "https://www20.a8.net/svt/bgt?aid=261021949728&wid=001&eno=01&mid=s00000000018047042000&mc=1")
        self.assertIsNone(offers["value-ai-writer"]["image"])
        self.assertEqual(offers["value-ai-writer"]["link"], A8 + "4BEO5P+CLOBQQ+1JUK+1HL85U")
        for program, (code, pixel) in LIVE_TEXT_LINKS.items():
            with self.subTest(program=program):
                self.assertEqual(links[program]["url"], A8 + code)
                self.assertEqual(links[program]["pixel"], pixel)
        self.assertEqual(links["ConoHa AI Canvas"]["aliases"], ["ConoHa AI Canvas"])

    def test_a8_material_wins_over_tsv_row(self):
        tsv = self.root / "in.tsv"
        # TSV 側は別の素材（…7RTY1E）。PARTNERS の a8（…7S2QE9）を使うこと
        tsv.write_text("s00000000018047\tConoHa AI Canvas\t\tfee\t4BELTP+C1FL6A+50+7RTY1E\t18\tanchor\t300×250\t23\t261021949728,001,01,s00000000018047040000,1\n", encoding="utf-8")
        with patch.multiple(a8_import, TSV=tsv, LINKS=self.root / "affiliate_links.json", OFFERS=self.root / "offers.json"), redirect_stdout(io.StringIO()):
            self.assertEqual(a8_import.main(), 0)
        offers = json.loads((self.root / "offers.json").read_text("utf-8"))["partners"]
        self.assertEqual(offers["conoha-ai-canvas"]["link"], A8 + "4BELTP+C1FL6A+50+7S2QE9")


if __name__ == "__main__":
    unittest.main()
