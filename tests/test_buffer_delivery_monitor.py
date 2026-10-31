"""Delivery monitoring is read-only; no SNS or network calls."""
import io
import sys
import unittest
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_delivery_monitor as monitor

NOW = datetime(2026, 10, 31, 2, 0, tzinfo=timezone.utc)


def node(pid, channel, status, due='2026-10-31T01:30:00Z', error=None, image=None):
    return {'id': pid, 'channelId': channel, 'status': status, 'dueAt': due,
            'createdAt': '2026-10-31T01:00:00Z', 'sentAt': '2026-10-31T01:31:00Z' if status == 'sent' else None, 'error': error, 'assets': [],
            'metadata': {'thread': [{'assets': ([{'type':'image','source':image}] if image else [])}]}}


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.original = monitor.buffer_graphql
        self.channels = [{'id': 't', 'service': 'threads'}, {'id': 'x', 'service': 'twitter'}, {'id': 'f', 'service': 'facebook'}]
        self.sent = [node('a', 't', 'sent'), node('b', 'x', 'sent')]
        self.pending = [node('c', 't', 'error', error={'rawError':'Image URL 404'}),
                        node('d', 'x', 'scheduled', due='2026-10-31T02:30:00Z', image='https://ai-tech-express.jp/card/a')]

    def fake(self, key, query, variables=None):
        self.assertNotIn('mutation', query.lower())
        if 'account {' in query:
            return {'account': {'organizations':[{'id':'org'}]}}
        if 'channels(input:' in query:
            return {'channels':self.channels}
        if 'posts(first:' in query:
            result = self.sent if 'status: [sent]' in query else self.pending
            return {'posts':{'edges':[{'node':p} for p in result], 'pageInfo':{'hasNextPage':False, 'endCursor':None}}}
        raise AssertionError('unexpected read')

    def test_counts_are_distinct_and_no_mutation(self):
        with patch.object(monitor, 'buffer_graphql', side_effect=self.fake):
            report=monitor.collect('fake', NOW, image_checker=lambda url: 'ok')
        self.assertEqual(report['counts']['threads']['sent'],1)
        self.assertEqual(report['counts']['threads']['error'],1)
        self.assertEqual(report['counts']['twitter']['scheduled'],1)
        self.assertEqual(report['errors']['画像取得関連'],1)
        self.assertEqual(report['images']['ok'],1)
        self.assertEqual(report['recent_errors'],1)
        text=monitor.render(report,NOW)
        self.assertNotIn('https://ai-tech-express.jp/card/a',text)
        self.assertNotIn('Image URL 404',text)

    def test_old_error_is_not_recent_and_missing_date_is_unknown(self):
        self.pending=[node('c','t','error',due='2026-10-28T00:00:00Z', error={'rawError':'404 media'})]
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            self.assertEqual(monitor.collect('fake',NOW)['recent_errors'],0)
        self.pending[0]['dueAt']=None
        self.pending[0]['createdAt']=None
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            self.assertEqual(monitor.collect('fake',NOW)['recent_errors'],1)

    def test_overdue_scheduled_and_buffer_unknown_fail_closed(self):
        self.pending=[node('c','t','scheduled',due='2026-10-31T01:00:00Z')]
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            self.assertEqual(monitor.collect('fake',NOW)['overdue'],1)
        with patch.object(monitor,'buffer_graphql',side_effect=RuntimeError('sensitive provider error')), patch.dict('os.environ', {'BUFFER_API_KEY':'fake'}, clear=True), patch('sys.stdout',new_callable=io.StringIO) as stdout:
            self.assertEqual(monitor.main(),2)
            self.assertNotIn('sensitive provider error',stdout.getvalue())

    def test_unverifiable_empty_provider_listing_fails_closed(self):
        self.sent=[]; self.pending=[]
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            with self.assertRaises(ValueError): monitor.collect('fake',NOW)

    def test_missing_channel_and_repeated_cursor_raise(self):
        self.channels=self.channels[:2]
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            with self.assertRaises(ValueError): monitor.collect('fake',NOW)
        page={'posts': {'edges': [], 'pageInfo': {'hasNextPage':True,'endCursor':'same'}}}
        with patch.object(monitor,'buffer_graphql',return_value=page):
            with self.assertRaises(ValueError): monitor.query_posts('fake','org',['t'],['sent'])

    def test_conflicting_duplicate_id_is_not_success(self):
        self.pending=[node('a','t','error')]
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            with self.assertRaises(ValueError): monitor.collect('fake',NOW)

    def test_image_fetch_allowlist_redirect_html_and_magic(self):
        opener=MagicMock()
        resp=MagicMock(); resp.__enter__.return_value=resp; resp.status=200
        resp.headers={'Content-Type':'image/png'}; resp.read.return_value=b'\x89PNG\r\n\x1a\n' + b'0'*8
        opener.open.return_value=resp
        with patch.object(monitor.urllib.request,'build_opener',return_value=opener):
            self.assertEqual(monitor.check_image('https://ai-tech-express.jp/card/x'),'ok')
            resp.read.return_value=b'<html>challenge'
            self.assertEqual(monitor.check_image('https://ai-tech-express.jp/card/x'),'unavailable')
            self.assertEqual(monitor.check_image('https://evil.example/x'),'external_unchecked')
            self.assertEqual(monitor.check_image('http://ai-tech-express.jp/x'),'external_unchecked')
            opener.open.side_effect=urllib.error.HTTPError('https://ai-tech-express.jp/x',302,'redirect',{},None)
            self.assertEqual(monitor.check_image('https://ai-tech-express.jp/card/x'),'unavailable')
        self.assertEqual(opener.open.call_count,3)

    def test_url_dedup_and_image_priority(self):
        self.pending=[node('c','t','scheduled',due='2026-10-31T02:30:00Z',image='https://ai-tech-express.jp/card/a'),node('d','x','scheduled',due='2026-10-31T02:30:00Z',image='https://ai-tech-express.jp/card/a')]
        seen=[]
        with patch.object(monitor,'buffer_graphql',side_effect=self.fake):
            r=monitor.collect('fake',NOW,image_checker=lambda url: seen.append(url) or 'unavailable')
        self.assertEqual(len(seen),1)
        self.assertEqual(r['images']['unavailable'],1)

if __name__=='__main__':
    unittest.main()
