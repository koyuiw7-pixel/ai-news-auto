"""Meta日本ニュース一覧を公式URLと照合し、未掲載候補を報告する（投稿・生成はしない）。"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
LANDING = 'https://about.fb.com/ja/news/'
UA = 'Mozilla/5.0 (compatible; SaisokuCoverageAudit/1.0; +https://ai-tech-express.jp)'
ARTICLE = re.compile(r'^https://about\.fb\.com/ja/news/20\d\d/\d\d/[^/]+/$')
TOPIC = re.compile(r'(?<![A-Za-z])AI(?![A-Za-z])|Muse|生成AI|人工知能|エージェント', re.I)


def normalize(url: str) -> str:
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'about.fb.com':
        return ''
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip('/')+'/', '', ''))


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.current = None; self.items = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            url = normalize(dict(attrs).get('href', ''))
            self.current = [url, []] if ARTICLE.fullmatch(url) else None
    def handle_data(self, text):
        if self.current:
            self.current[1].append(text)
    def handle_endtag(self, tag):
        if tag == 'a' and self.current:
            url, texts = self.current
            title = ' '.join(' '.join(texts).split())
            if title:
                self.items.append({'url': url, 'title': title})
            self.current = None


def parse(page: str) -> list[dict]:
    parser = Links(); parser.feed(page)
    seen = set(); items = []
    for item in parser.items:
        if item['url'] not in seen:
            seen.add(item['url']); items.append(item)
    if not items:
        raise ValueError('Meta日本ニュースの記事リンクが見つかりません')
    return items


def known_sources(content_root: Path) -> set[str]:
    known = set()
    for folder in ('articles', 'howto'):
        for path in (content_root / folder).glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            for candidate in [data.get('sourceUrl'), *(x.get('url') for x in data.get('sources', []) if isinstance(x, dict))]:
                if isinstance(candidate, str) and (url := normalize(candidate)):
                    known.add(url)
    return known


def audit(page: str, known: set[str]) -> dict:
    all_items = parse(page)
    relevant = [i for i in all_items if TOPIC.search(i['title'])]
    return {'checkedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'scope': 'Meta日本ニュースの一覧ページのみ。履歴全体ではない',
            'totalLinks': len(all_items), 'relevant': [dict(i, covered=i['url'] in known) for i in relevant]}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    try:
        req = urllib.request.Request(LANDING, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError('listing too large')
        report = audit(data.decode('utf-8'), known_sources(ROOT / 'content'))
        error = False
    except Exception as exc:
        report = {'checkedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'status': 'error', 'error': type(exc).__name__}
        error = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))
    return 1 if error else 0

if __name__ == '__main__':
    sys.exit(main())
