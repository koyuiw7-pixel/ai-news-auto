"""広告主の公開商品情報を読み取り、価格・在庫の確認状況をレポートする。広告リンクは呼ばない。"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = 'Mozilla/5.0 (compatible; SaisokuProductAudit/1.0; +https://ai-tech-express.jp)'
MAX_BYTES = 2_000_000


def parse_plaud(data: dict) -> tuple[int | None, str]:
    name = str(data.get('title', '')).strip().casefold()
    variants = data.get('variants')
    if not name or not isinstance(variants, list) or not variants:
        return None, 'unknown'
    chosen = []
    for variant in variants:
        title = str(variant.get('title', '')).strip()
        if not title:
            return None, 'unknown'
        if '/' in title and title.split('/', 1)[0].strip().casefold() != name:
            continue
        if '/' not in title and re.search(r'edition|エディション', title, re.I):
            continue
        price, available = variant.get('price'), variant.get('available')
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0 or price % 100 or not isinstance(available, bool):
            return None, 'unknown'
        chosen.append((price // 100, available))
    if not chosen:
        return None, 'unknown'
    prices = {price for price, _ in chosen}
    return (next(iter(prices)) if len(prices) == 1 else None), ('available' if any(a for _, a in chosen) else 'sold_out')


def parse_oz(page: str) -> tuple[int | None, str]:
    match = re.search(r'makeshop-item-price:1">([\d,]+)', page)
    price = int(match.group(1).replace(',', '')) if match else None
    sold = bool(re.search(r'class="floating-buy-bar[^\"]*\bis-soldout\b', page, re.I))
    available = bool(re.search(r'class="item-stock"[^>]*>\s*在庫あり\s*<', page, re.I))
    return price, 'unknown' if sold == available else ('sold_out' if sold else 'available')


def fetch_source(source: str) -> tuple[int | None, str]:
    kind, sep, ident = source.partition(':')
    if not sep:
        raise ValueError('invalid source')
    if kind == 'plaud' and re.fullmatch(r'[a-z0-9-]+', ident):
        url = f'https://jp.plaud.ai/products/{ident}.js'
    elif kind == 'oz' and re.fullmatch(r'\d{12}', ident):
        url = f'https://www.ozgaming-pcshop.com/view/item/{ident}'
    else:
        raise ValueError('unsupported source')
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError('source exceeded size limit')
    text = payload.decode('utf-8')
    return parse_plaud(json.loads(text)) if kind == 'plaud' else parse_oz(text)


def audit(offers: dict, products: dict, *, fetcher=fetch_source, checked_at=None) -> dict:
    records = []
    observed_at = datetime.fromisoformat(checked_at) if checked_at else datetime.now(timezone.utc)
    for key, partner in offers.get('partners', {}).items():
        source = partner.get('source')
        stored = products.get('partnerPrices', {}).get(key, partner.get('price'))
        row = {'key': key, 'name': partner.get('name'), 'hidden': bool(partner.get('hidden')),
               'sourceConfigured': bool(source), 'storedPrice': stored, 'observedPrice': None,
               'availability': 'unknown', 'result': 'not_monitored'}
        expiry = partner.get('activeUntil')
        try:
            expired = bool(expiry and datetime.fromisoformat(expiry) <= observed_at)
        except (TypeError, ValueError):
            expired = False
        row['expired'] = expired
        if source:
            try:
                price, availability = fetcher(source)
                row.update(observedPrice=price, availability=availability,
                           result='verified' if price is not None and availability != 'unknown' else 'incomplete')
                if price is not None and stored is not None and price != stored:
                    row['priceChanged'] = True
                if availability == 'sold_out' and not row['hidden'] and not expired:
                    row['needsReview'] = 'sold_out_but_visible'
                elif row.get('priceChanged') and not row['hidden'] and not expired:
                    row['needsReview'] = 'price_changed'
            except Exception as error:
                row.update(result='error', error=type(error).__name__)
        records.append(row)
    return {'checkedAt': observed_at.isoformat(timespec='seconds'),
            'catalogFetchedAt': products.get('fetchedAt'), 'results': records,
            'counts': {key: sum(r['result'] == key for r in records) for key in ('verified','incomplete','error','not_monitored')},
            'reviewCount': sum('needsReview' in r for r in records)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    data = audit(json.loads((ROOT/'content/offers.json').read_text()), json.loads((ROOT/'content/products.json').read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'counts': data['counts'], 'reviewCount': data['reviewCount'], 'checkedAt': data['checkedAt']}, ensure_ascii=False))
    return 0 if not data['counts']['error'] and not data['counts']['incomplete'] and not data['reviewCount'] else 1

if __name__ == '__main__':
    sys.exit(main())
