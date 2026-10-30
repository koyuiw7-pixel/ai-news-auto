"""既存回答を守る適用境界。公式取得はfixtureで置換し外部通信しない。"""
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dify_answer_update as update
import dify_search_watch as watch


class DifyAnswerUpdateTest(unittest.TestCase):
    observed = '2026-10-31T01:00:00+00:00'
    checked = '2026-10-31T01:05:00+00:00'
    now = datetime.fromisoformat('2026-10-31T01:10:00+00:00')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'content/howto').mkdir(parents=True)
        for slug in update.GUIDES:
            guide = {
                'slug': slug, 'refreshMode': 'editorial', 'title': 'Existing title',
                'intro': 'Existing introduction', 'conclusion': ['Existing conclusion'],
                'faq': [{'q': 'APIキーとクレジットの料金は？', 'a': 'Existing answer'},
                        {'q': '起動に失敗したら？', 'a': 'Existing startup answer'}],
                'steps': [{'title': 'Step', 'body': 'Existing body', 'commands': ['docker compose ps']}],
                'pricing': [{'price': 'Original price'}], 'products': ['keep-product'],
                'decisionGuideSlug': 'dify-hosting', 'advertisement': 'https://px.a8.net/svt/ejp?a8mat=KEEP',
                'createdAt': '2026-10-30T01:00:00+00:00', 'updatedAt': '2026-10-30T02:00:00+00:00',
                'checkedAt': '2026-10-30T01:00:00+00:00', 'needsReview': True,
                'sources': [{'url': 'https://docs.dify.ai', 'checkedAt': '2026-10-30'}],
            }
            self.path(slug).write_text(json.dumps(guide, ensure_ascii=False) + '\n')
        self.raw = {
            'model-providers': b'# Model Providers\n## Use Models with Your AI Credits\n2 AI credits per model call.\n## Use Your Own Account with a Supported Provider\nSet Usage Priority.',
            'knowledge-request-rate-limit': b'# Knowledge Request Rate Limit\n## What Counts\nRetrieval counts.\n## When You Reach the Limit\nWait a minute.',
            'docker-compose': b'# Deploy Dify with Docker Compose\n## Before Deployment\nUse official configuration.',
            'deployment-faqs': b'# FAQs\n## Clone Fails with Remote branch null not found\nCheck the API rate limit.',
            'release': json.dumps({'tag_name': '1.18.0', 'name': 'Release', 'body': 'Before upgrade, back up the database and files.', 'draft': False, 'prerelease': False, 'html_url': 'https://github.com/langgenius/dify/releases/tag/1.18.0'}).encode(),
        }
        self.state, _ = watch.run_watch({}, self.observed, self.fetch)
        self.packet = update.packet_for(self.state, 'model-providers', self.root)
        self.packet['review'].update(reviewer='Codex evidence review', checkedAt=self.checked,
                                     decision='approved', rationale='Official source reviewed against existing answer.',
                                     meaningAndPricingReviewed=True, versionAndAudienceReviewed=True)
        self.packet['edits'] = [{'path': '/faq/-', 'before': None,
                                 'after': {'q': '追加の質問は？', 'a': '公式の条件を確認して判断します。'}}]

    def path(self, slug='dify-free-api-cost'):
        return self.root / 'content/howto' / (slug + '.json')

    def fetch(self, source):
        self.assertIn(source['id'], self.raw)
        self.assertEqual(source, update.SOURCES[source['id']])
        return self.raw[source['id']]

    def apply(self, packet=None, **kwargs):
        return update.apply_review(packet or self.packet, self.state, root=self.root, now=self.now,
                                   fetcher=kwargs.pop('fetcher', self.fetch), **kwargs)

    def assert_blocked_unchanged(self, packet=None, **kwargs):
        before = self.path().read_bytes()
        with self.assertRaises((ValueError, KeyError, TypeError, OSError)):
            self.apply(packet, dry_run=False, **kwargs)
        self.assertEqual(self.path().read_bytes(), before)

    def test_baseline_has_no_change_packet_manual_is_explicit_hypothesis(self):
        before = self.path().read_bytes()
        result = update.propose(self.state, self.root)
        self.assertEqual(result['packets'], [])
        for source_id in self.raw:
            packet = update.propose(self.state, self.root, source_id)['packets'][0]
            self.assertEqual(packet['trigger'], 'manual_current_source_review')
            self.assertIsNone(packet['source']['previousHash'])
            self.assertEqual(packet['demandStatus'], 'hypothesis_not_measured')
            self.assertEqual(packet['edits'], [])
            self.assertTrue(packet['guide']['measurementPath'].startswith('/guides/dify-'))
        self.assertEqual(self.path().read_bytes(), before)

    def test_default_dry_run_and_apply_preserve_every_unowned_field(self):
        before = self.path().read_bytes()
        self.assertEqual(self.apply()['status'], 'validated_dry_run')
        self.assertEqual(self.path().read_bytes(), before)
        self.assertEqual(self.apply(dry_run=False)['published'], False)
        old, new = json.loads(before), json.loads(self.path().read_bytes())
        for key in old:
            if key not in {'faq', 'updatedAt'}:
                self.assertEqual(new[key], old[key], key)
        self.assertEqual(new['faq'][:-1], old['faq'])
        history = new['answerUpdateHistory'][0]
        self.assertEqual(history['sourceHash'], self.packet['source']['sourceHash'])
        self.assertEqual(history['articleBeforeHash'], update.digest(before))
        self.assertEqual(history['paths'], ['/faq/-'])
        self.assert_blocked_unchanged()

    def test_explicit_review_and_nonfuture_timestamp_required(self):
        changes = [ {'decision': ''}, {'reviewer': ''}, {'rationale': ''},
                    {'meaningAndPricingReviewed': False}, {'versionAndAudienceReviewed': False},
                    {'checkedAt': '2026-10-31T01:00:00'}, {'checkedAt': '2026-10-31T00:00:00+00:00'},
                    {'checkedAt': '2026-10-31T01:11:00+00:00'} ]
        for fields in changes:
            with self.subTest(fields=fields):
                packet = copy.deepcopy(self.packet)
                packet['review'].update(fields)
                self.assert_blocked_unchanged(packet)

    def test_hand_edit_or_tampered_source_and_identity_cannot_be_overwritten(self):
        for group, key, value in [('guide', 'articleHash', '0' * 64), ('source', 'sourceHash', '0' * 64),
                                  ('source', 'url', 'https://example.com/not-official'),
                                  ('guide', 'slug', '../other'), ('guide', 'path', '/tmp/other')]:
            with self.subTest(key=key):
                packet = copy.deepcopy(self.packet)
                packet[group][key] = value
                self.assert_blocked_unchanged(packet)
        self.path().write_text(self.path().read_text() + ' ')
        self.assert_blocked_unchanged()

    def test_source_change_or_fetch_failure_never_writes(self):
        self.raw['model-providers'] += b'\nThe official conditions changed.'
        self.assert_blocked_unchanged()
        def failing(source):
            raise OSError('unavailable')
        self.assert_blocked_unchanged(fetcher=failing)

    def test_protected_fields_and_invalid_before_are_rejected(self):
        for path in ['/pricing/0/price', '/steps/0/commands/0', '/slug', '/sources/0/url', '/advertisement',
                     '/createdAt', '/checkedAt', '/refreshMode', '/faq/-1/a', '/../other']:
            with self.subTest(path=path):
                packet = copy.deepcopy(self.packet)
                packet['edits'] = [{'path': path, 'before': None, 'after': 'New value'}]
                self.assert_blocked_unchanged(packet)
        packet = copy.deepcopy(self.packet)
        packet['edits'] = [{'path': '/faq/0/a', 'before': 'not original', 'after': 'Updated answer'}]
        self.assert_blocked_unchanged(packet)

    def test_plain_text_only_no_html_controls_or_ad_links(self):
        for text in ['</script><script>alert(1)</script>', '<b>Answer</b>', 'unsafe\u0000text',
                     'unsafe\u000btext', 'https://px.a8.net/svt/ejp?a8mat=NEW', 'https://amazon.co.jp/item']:
            with self.subTest(text=text):
                packet = copy.deepcopy(self.packet)
                packet['edits'][0]['after']['a'] = text
                self.assert_blocked_unchanged(packet)
        guide = json.loads(self.path().read_bytes())
        guide['faq'][0]['a'] = 'Existing https://px.a8.net/svt/ejp?a8mat=KEEP'
        with self.assertRaises(ValueError):
            update.edited_guide(guide, [{'path': '/faq/0/a', 'before': guide['faq'][0]['a'], 'after': 'Removed link'}])

    def test_duplicate_question_and_edit_paths_are_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet['edits'][0]['after']['q'] = 'APIキーとクレジットの料金は？'
        self.assert_blocked_unchanged(packet)
        packet = copy.deepcopy(self.packet)
        packet['edits'].append(copy.deepcopy(packet['edits'][0]))
        self.assert_blocked_unchanged(packet)

    def test_corrupt_snapshot_non_editorial_and_symlink_fail_closed(self):
        state = copy.deepcopy(self.state)
        state['sources']['model-providers']['text'] += ' altered'
        with self.assertRaises(ValueError):
            update.propose(state, self.root, 'model-providers')
        guide = json.loads(self.path().read_bytes())
        guide['refreshMode'] = 'auto'
        self.path().write_text(json.dumps(guide))
        self.assert_blocked_unchanged()
        self.path().unlink()
        self.path().symlink_to(self.path('dify-1-18-startup-check'))
        with self.assertRaises(ValueError):
            update.load_guide(self.root, 'dify-free-api-cost')

    def test_detected_candidate_routes_to_matching_faq_then_completed_is_not_reproposed(self):
        self.raw['model-providers'] = self.raw['model-providers'].replace(b'2 AI credits', b'3 AI credits')
        self.state, _ = watch.run_watch(self.state, self.observed, self.fetch)
        packets = update.propose(self.state, self.root)['packets']
        self.assertEqual(len(packets), 1)
        packet = packets[0]
        self.assertEqual(packet['trigger'], 'detected_source_change')
        self.assertEqual(packet['faqMatches'][0]['path'], '/faq/0/a')
        packet['review'] = copy.deepcopy(self.packet['review'])
        packet['edits'] = [{'path': '/faq/0/a', 'before': 'Existing answer', 'after': 'Reviewed replacement'}]
        self.apply(packet, dry_run=False)
        next_result = update.propose(self.state, self.root)
        self.assertEqual(next_result['packets'], [])
        self.assertEqual(next_result['completed'][0]['candidateId'], packet['candidateId'])
        self.raw['model-providers'] += b'\nAI credits may vary by model.'
        self.state, _ = watch.run_watch(self.state, self.observed, self.fetch)
        next_result = update.propose(self.state, self.root)
        self.assertEqual(len(next_result['packets']), 1)
        self.assertEqual(next_result['blocked'], [])
        self.assertEqual(next_result['completed'][0]['candidateId'], packet['candidateId'])

    def test_concurrent_hand_edit_during_refetch_is_preserved(self):
        guide = json.loads(self.path().read_bytes())
        guide['intro'] = 'A later human edit'
        raw = json.dumps(guide).encode()
        def concurrently_editing(source):
            self.path().write_bytes(raw)
            return self.fetch(source)
        with self.assertRaises(ValueError):
            self.apply(dry_run=False, fetcher=concurrently_editing)
        self.assertEqual(self.path().read_bytes(), raw)

    def test_apply_preserves_existing_article_timezone(self):
        guide = json.loads(self.path().read_bytes())
        guide['updatedAt'] = '2026-10-30T11:00:00+09:00'
        self.path().write_text(json.dumps(guide))
        packet = update.packet_for(self.state, 'model-providers', self.root)
        packet['review'], packet['edits'] = self.packet['review'], self.packet['edits']
        self.apply(packet, dry_run=False)
        updated = json.loads(self.path().read_bytes())['updatedAt']
        self.assertEqual(updated, '2026-10-31T10:10:00+09:00')
        self.assertEqual(datetime.fromisoformat(updated), self.now)

    def test_packet_output_cannot_overwrite_content_state_code_or_other_work(self):
        state_path = self.root / 'work/state.json'
        state_path.parent.mkdir()
        state_path.write_text(json.dumps(self.state))
        packet = update.propose(self.state, self.root)
        with patch.object(update, 'ROOT', self.root):
            targets = [self.path(), state_path, self.root / 'scripts/work/code.json',
                       self.root / 'state/work/state.json', self.root / 'output.json']
            other = self.root / 'work/valuable.json'
            other.write_text('{"keep":"original"}')
            targets.append(other)
            link = self.root / 'work/link.json'
            link.symlink_to(self.path())
            targets.append(link)
            for target in targets:
                with self.subTest(target=target):
                    before = target.read_bytes() if target.exists() else None
                    with self.assertRaises(ValueError):
                        update.write_packet(target, state_path, packet)
                    self.assertEqual(target.read_bytes() if target.exists() else None, before)
            valid = self.root / 'work/review.json'
            update.write_packet(valid, state_path, packet)
            update.write_packet(valid, state_path, packet)
            self.assertEqual(json.loads(valid.read_text()), packet)

    def test_state_identity_is_required(self):
        path = self.root / 'state.json'
        for state in [{}, {**self.state, 'sourceFingerprint': 'wrong'}]:
            path.write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                update.read_state(path)
        path.write_text(json.dumps(self.state))
        self.assertEqual(update.read_state(path), self.state)


if __name__ == '__main__':
    unittest.main()
