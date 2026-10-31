"""PRの表現がA8提携情報の再取込で元に戻らないことを、通信なしで確かめる。"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import a8_import


class PrCopyTest(unittest.TestCase):
    def test_importer_and_live_offer_copy_match(self):
        offers = json.loads((ROOT / 'content/offers.json').read_text(encoding='utf-8'))['partners']
        items = {item['key']: item for item in a8_import.PARTNERS.values()}
        for key in ('xserver', 'silicon-power', 'video-editor', 'virusbuster', 'aio-diagnosis'):
            with self.subTest(key=key):
                self.assertEqual(items[key]['label'], offers[key]['label'])
                self.assertEqual(items[key]['note'], offers[key]['note'])


if __name__ == '__main__':
    unittest.main()
