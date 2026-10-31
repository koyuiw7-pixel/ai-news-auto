#!/usr/bin/env python3
"""Read-only confidential Buffer error audit; caller encrypts output."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import threads_post as tp

FIELDS = '''id text status createdAt dueAt sentAt externalLink channelId
error { message rawError supportUrl }
metadata { __typename
 ... on ThreadsPostMetadata { linkAttachment {url} thread {text metadata {threads {linkAttachment {url}}}} }
 ... on TwitterPostMetadata {thread {text}}
}'''
TARGET_IDS = ['6ae1e674dee6d1a87ac2bb0e', '6ae1e67e38e33389fb60a63a', '6ae0cb1b960a519e24d0ea79', '6ae0cb10c689d991f0b91bb4']

def audit(key):
    if not key:
        raise ValueError('Buffer credential unavailable')
    result = {'complete': False, 'target_posts': {}, 'organizations': [], 'schema': {}}
    for type_name in ('Post', 'PostAssets', 'Asset', 'ThreadsPostMetadata', 'TwitterPostMetadata'):
        try:
            result['schema'][type_name] = tp.buffer_graphql(key, 'query($name: String!) { __type(name: $name) { name fields { name type { kind name ofType { kind name ofType { kind name } } } } } }', {'name': type_name}).get('__type')
        except Exception as exc:
            result['schema'][type_name] = {'error': str(exc)[:300]}
    for post_id in TARGET_IDS:
        try:
            result['target_posts'][post_id] = tp.buffer_graphql(key, 'query($id: PostId!) { post(input: { id: $id }) { ' + FIELDS + ' } }', {'id': post_id}).get('post')
        except Exception as exc:
            result['target_posts'][post_id] = {'lookup_error': str(exc)[:1000]}
    orgs = tp.buffer_graphql(key, 'query { account { organizations { id } } }')['account']['organizations']
    for org in orgs:
        oid = org['id']
        channels = tp.buffer_graphql(key, f'query {{ channels(input: {{ organizationId: {json.dumps(oid)} }}) {{ id name displayName service }} }}')['channels']
        included = [c for c in channels if str(c.get('service', '')).lower() in ('threads', 'twitter')]
        entry = {'channels': included, 'posts': [], 'pages': 0, 'complete': False}
        result['organizations'].append(entry)
        if not included:
            entry['complete'] = True
            continue
        cursor, seen = None, set()
        for page in range(100):
            after = ', after: ' + json.dumps(cursor) if cursor else ''
            q = f'''query {{ posts(first: 50{after}, input: {{ organizationId: {json.dumps(oid)}, filter: {{ status: [scheduled, sending, needs_approval, draft, error], channelIds: {json.dumps([c['id'] for c in included])} }} }}) {{ edges {{ node {{ {FIELDS} }} }} pageInfo {{endCursor hasNextPage}} }} }}'''
            data = tp.buffer_graphql(key, q)['posts']
            entry['posts'].extend(e['node'] for e in data['edges'])
            entry['pages'] = page + 1
            if not data['pageInfo']['hasNextPage']:
                entry['complete'] = True
                break
            nxt = data['pageInfo']['endCursor']
            if not nxt or nxt in seen:
                raise ValueError('Invalid or repeated pagination cursor')
            seen.add(nxt)
            cursor = nxt
        else:
            raise ValueError('Pagination limit exceeded')
    result['complete'] = bool(orgs) and all(x['complete'] for x in result['organizations'])
    return result

def main():
    try:
        result = audit(os.environ.get('BUFFER_API_KEY', '').strip())
    except Exception as exc:
        result = {'complete': False, 'error_type': type(exc).__name__, 'error': str(exc)[:1500]}
    Path(os.environ['AUDIT_RESULT']).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
if __name__ == '__main__':
    main()
