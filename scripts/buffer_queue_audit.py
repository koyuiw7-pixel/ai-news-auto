#!/usr/bin/env python3
"""Read-only Buffer queue inventory; writes confidential result only to a caller-provided file.

Uses the existing Buffer credential and GraphQL read operations only. Never logs post data.
The caller must encrypt the output before exporting it from a runner.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import threads_post as tp


def audit(api_key: str) -> dict:
    if not api_key:
        raise ValueError('Buffer credential unavailable')
    orgs = tp.buffer_graphql(api_key, 'query { account { organizations { id } } }')['account']['organizations']
    if not orgs:
        raise ValueError('No organizations returned')
    result = {'complete': False, 'organizations': []}
    for org in orgs:
        oid = org['id']
        channels = tp.buffer_graphql(api_key, f'query {{ channels(input: {{ organizationId: {json.dumps(oid)} }}) {{ id name displayName service }} }}')['channels']
        included = [c for c in channels if str(c.get('service', '')).lower() in ('threads', 'twitter', 'facebook')]
        entry = {'channels': included, 'posts': [], 'pages': 0}
        if included:
            ids = [c['id'] for c in included]
            cursor = None
            seen = set()
            for page in range(100):
                after = ', after: ' + json.dumps(cursor) if cursor else ''
                query = f'''query {{ posts(first: 50{after}, input: {{ organizationId: {json.dumps(oid)}, filter: {{ status: [scheduled, sending, needs_approval, draft, error], channelIds: {json.dumps(ids)} }} }}) {{
                  edges {{ node {{ id text status dueAt channelId externalLink metadata {{ __typename
                    ... on ThreadsPostMetadata {{ linkAttachment {{ url }} thread {{ text metadata {{ threads {{ linkAttachment {{ url }} }} }} }} }}
                    ... on TwitterPostMetadata {{ thread {{ text }} }}
                    ... on FacebookPostMetadata {{ firstComment linkAttachment {{ url }} }}
                  }} }} }} pageInfo {{ endCursor hasNextPage }} }} }}'''
                data = tp.buffer_graphql(api_key, query)['posts']
                entry['posts'].extend(e['node'] for e in data['edges'])
                entry['pages'] = page + 1
                if not data['pageInfo']['hasNextPage']:
                    break
                nxt = data['pageInfo']['endCursor']
                if not nxt or nxt in seen:
                    raise ValueError('Invalid or repeated pagination cursor')
                seen.add(nxt)
                cursor = nxt
            else:
                raise ValueError('Pagination limit exceeded')
        result['organizations'].append(entry)
    result['complete'] = True
    return result


def main() -> int:
    try:
        result = audit(os.environ.get('BUFFER_API_KEY', '').strip())
    except Exception as error:
        result = {'complete': False, 'error_type': type(error).__name__, 'error': str(error)[:500]}
    Path(os.environ['AUDIT_RESULT']).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
