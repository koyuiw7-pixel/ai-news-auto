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


    def _copy(self, key):
        offers = json.loads((ROOT / 'content/offers.json').read_text(encoding='utf-8'))['partners']
        item = offers[key]
        pitch = item.get('pitch', {})
        return ' '.join([item.get('name', ''), item['label'], item['note'], pitch.get('fit', ''), pitch.get('point', ''),
                         pitch.get('cta', ''), pitch.get('gain', ''), *pitch.get('merits', [])])

    def test_enepi_copy_says_registration_is_needed(self):
        # enepi.jp「※電気料金の比較・相談はエネピへ登録が必要です。」（2026-11-10）
        text = self._copy('enepi')
        self.assertIn('登録', text)
        self.assertNotIn('比べられる比較サービス', text)
        offers = json.loads((ROOT / 'content/offers.json').read_text(encoding='utf-8'))['partners']
        self.assertNotEqual(offers['enepi']['label'], '電気料金を比べる')
        self.assertNotEqual(offers['enepi']['pitch']['cta'], '電気料金を比べる')

    def test_surfshark_copy_is_the_antivirus_programme(self):
        # 提携は Surfshark Antivirus。VPN や台数無制限は別の商品の話
        text = self._copy('surfshark')
        self.assertNotIn('VPN', text)
        self.assertNotIn('無制限', text)
        self.assertIn('ウイルス', text)

    def test_no_partner_copy_has_bar_point_rebate_or_reward(self):
        import re
        tsv = ROOT / '.claude' / 'a8_partnered.tsv'
        rows = [line.split('\t') for line in tsv.read_text(encoding='utf-8').splitlines()] if tsv.exists() else []
        fees = {re.sub(r'^[^0-9]*', '', row[3]) for row in rows if len(row) > 3 and re.search(r'\d', row[3])}
        fees = {fee for fee in fees if len(fee) >= 4}
        for meta in a8_import.PARTNERS.values():
            key = meta['key']
            texts = [meta['name'], meta['label'], meta['note'], a8_import.GAIN.get(key, ''), *a8_import.MERITS.get(key, []),
                     *a8_import.PITCH.get(key, {}).values()]
            with self.subTest(key=key):
                for text in texts:
                    self.assertNotIn('｜', text)
                    self.assertNotIn('ポイント還元', text)
                    self.assertNotIn('ざっくり', text)
                    self.assertNotIn('報酬', text)
                    # A8 の成果報酬（TSV の4列目、例「新規申込1271円」「購入30％」）を表に出さない
                    for fee in fees:
                        self.assertNotIn(fee, text)


if __name__ == '__main__':
    unittest.main()
