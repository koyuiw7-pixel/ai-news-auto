"""Bluesky の投稿選び（本数・間隔・埋め合わせ・重複よけ）を外部通信なしで検証する。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import bluesky_post as bp

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc)  # 13:00 JST


def iso(dt):
    return dt.isoformat(timespec='seconds')


def article(slug, title, minutes_ago=60, **extra):
    body = '## 日本で使える？\n' + 'あ' * 2000
    base = {'slug': slug, 'title': title, 'body': body, 'genreSlug': 'ai', 'tags': ['AI'],
            'generatedAt': iso(NOW - timedelta(minutes=minutes_ago)), 'description': 'd'}
    base.update(extra)
    return base


def mirror(minutes_ago, **extra):
    entry = {'style': 'standalone', 'dueAt': iso(NOW - timedelta(minutes=minutes_ago))}
    entry.update(extra)
    return entry


class SelectionHelpersTest(unittest.TestCase):
    def test_similar_titles(self):
        self.assertTrue(bp.similar('OpenAIが「GPT-6」を発表', 'GPT-6の詳細、OpenAI『GPT-6』公開'))
        self.assertFalse(bp.similar('AI半導体のNVIDIAが英国AI構想を発表 創薬からロボットまで変える次世代基盤',
                                    'AI半導体のNVIDIAが医療向けAI発表 創薬から手術支援まで自動化を促進'))

    def test_pending_skips_articles_already_posted_as_bluesky_only(self):
        state = {'posted': {'a': mirror(30)}}
        self.assertEqual(bp.pending(state, NOW, {'a': {'at': iso(NOW)}}), [])
        self.assertEqual([k for k, _ in bp.pending(state, NOW)], ['a'])


class MergeExtraTest(unittest.TestCase):
    def test_union_keeps_existing_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'extra.json'
            mine = Path(directory) / 'mine.json'
            target.write_text(json.dumps({'a': {'uri': 'remote', 'at': iso(NOW)}}))
            mine.write_text(json.dumps({'a': {'uri': 'mine', 'at': iso(NOW)}, 'b': {'uri': 'b', 'at': iso(NOW)}}))
            with patch.object(bp, 'EXTRA_PATH', target):
                bp.merge_extra(str(mine))
            merged = json.loads(target.read_text())
        self.assertEqual(merged['a']['uri'], 'remote')
        self.assertEqual(merged['b']['uri'], 'b')

    def test_missing_mine_file_is_harmless(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'extra.json'
            target.write_text(json.dumps({'a': {'uri': 'remote'}}))
            with patch.object(bp, 'EXTRA_PATH', target):
                bp.merge_extra(str(Path(directory) / 'none.json'))
            self.assertEqual(json.loads(target.read_text()), {'a': {'uri': 'remote'}})


if __name__ == '__main__':
    unittest.main()
