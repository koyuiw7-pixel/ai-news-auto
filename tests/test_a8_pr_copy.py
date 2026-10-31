"""PRの表現がA8提携情報の再取込で元に戻らないことを、通信なしで確かめる。"""
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
from contextlib import redirect_stdout
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import a8_import


class PrCopyTest(unittest.TestCase):
    def test_importer_and_live_offer_copy_match(self):
        offers = json.loads((ROOT / 'content/offers.json').read_text(encoding='utf-8'))['partners']
        items = {item['key']: item for item in a8_import.PARTNERS.values()}
        for key in ('xserver', 'silicon-power', 'video-editor', 'virusbuster', 'aio-diagnosis', 'xserver-vps', 'conoha-vps', 'movie-school', 'lancul', 'doraverse', 'surfshark'):
            with self.subTest(key=key):
                self.assertEqual(items[key]['label'], offers[key]['label'])
                self.assertEqual(items[key]['note'], offers[key]['note'])

    def test_import_preserves_editorial_safety_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tsv, links, offers = root / 'in.tsv', root / 'links.json', root / 'offers.json'
            tsv.write_text('s00000001642001\tname\tcat\tfee\tcode\t13\tanchor\tsize\t\t\n', encoding='utf-8')
            links.write_text('{}', encoding='utf-8')
            offers.write_text(json.dumps({'topics': [], 'partners': {'xserver': {
                'hidden': True, 'caution': '条件を確認', 'activeUntil': '2026-11-01T00:00:00+09:00'
            }}}), encoding='utf-8')
            with patch.multiple(a8_import, TSV=tsv, LINKS=links, OFFERS=offers), redirect_stdout(io.StringIO()):
                self.assertEqual(a8_import.main(), 0)
            result = json.loads(offers.read_text(encoding='utf-8'))['partners']['xserver']
            self.assertTrue(result['hidden'])
            self.assertEqual(result['caution'], '条件を確認')
            self.assertEqual(result['activeUntil'], '2026-11-01T00:00:00+09:00')


if __name__ == '__main__':
    unittest.main()
