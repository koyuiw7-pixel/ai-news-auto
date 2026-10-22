"""
記事末の「試すなら」枠に出す本を、楽天ブックスの売れ筋から話題ごとに選んで保存する。

- 話題の定義は content/offers.json（topics[].search）。
- 結果は content/products.json に書き出し、サイトはビルド時にそれを読む。
- リンクは A8.net 経由の楽天アフィリエイト（A8 の楽天商品リンクと同じ形式）。
- 価格・評価は取得時点のもの。サイト側で「◯月◯日時点」と明記する。

使い方:
    python3 scripts/rakuten_books.py          # 取得して保存
    python3 scripts/rakuten_books.py --dry    # 表示だけ
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFERS = ROOT / "content" / "offers.json"
PRODUCTS = ROOT / "content" / "products.json"

# A8.net「楽天アフィリエイト」提携で発行されたID（A8 管理画面の楽天商品リンクから取得）
A8MAT = "4BELTP+50ED2Q+2HOM+BWGDT"
RAKUTEN_HGC = "g00q0724.2bo11c45.g00q0724.2bo12179/a26102173090_4BELTP_50ED2Q_2HOM_BWGDT"
PIXEL = "https://www15.a8.net/0.gif?a8mat=" + A8MAT

USER_AGENT = "Mozilla/5.0 (compatible; SaisokuBot/1.0; +https://ai-tech-express.jp)"
PER_TOPIC = 3
MIN_YEAR = 2025


def affiliate_url(rb_id: str, item_id: str) -> str:
    """A8 の楽天商品リンクと同じ構造のURLを組み立てる。"""
    pc = f"https://item.rakuten.co.jp/book/{rb_id}/"
    mobile = f"http://m.rakuten.co.jp/book/i/{item_id}/"
    inner = (
        f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_HGC}"
        f"?pc={urllib.parse.quote(pc, safe='')}&m={urllib.parse.quote(mobile, safe='')}"
    )
    return (
        f"https://rpx.a8.net/svt/ejp?a8mat={A8MAT}&rakuten=y"
        f"&a8ejpredirect={urllib.parse.quote(inner, safe='')}"
    )


def image_url(src: str) -> str:
    """検索結果の画像（tshop.r10s.jp）を、楽天の商品リンクが使う公式サムネイルURLに揃える。"""
    match = re.search(r"/book/cabinet/([^?\"]+)", src)
    if not match:
        return ""
    return f"https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{match.group(1)}?_ex=400x400"


def fetch(keyword: str) -> str:
    url = (
        "https://books.rakuten.co.jp/search?"
        + urllib.parse.urlencode({"sitem": keyword, "g": "001", "s": "7"})
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse(page: str) -> list[dict]:
    items = []
    blocks = page.split('<div class="rbcomp__item-list__item"')[1:]
    for block in blocks:
        rb = re.search(r"books\.rakuten\.co\.jp/rb/(\d+)/", block)
        item = re.search(r'data-item-id="(\d+)"', block)
        title = re.search(r'item__title">(.*?)</span>', block, re.S)
        price = re.search(r'item__price">\s*<em>([\d,]+)円', block)
        img = re.search(r'<img src="([^"]+)"', block)
        if not (rb and item and title and price and img):
            continue
        if "stock1" not in block:  # 在庫ありだけ
            continue
        released = re.search(r"subtext\">\s*(\d{4})年(\d{2})月", block)
        rating = re.search(r"review__?[^>]*>\s*<span[^>]*></span>\s*<em>([\d.]+)</em>", block)
        reviews = re.search(r"レビュー(\d+)件", block)
        author = re.search(r'item__author">\s*<a[^>]*>(.*?)</a>', block, re.S)
        category = re.search(r'rbcomp__category ([a-z]+)', block)
        if category and category.group(1) != "book":
            continue
        items.append(
            {
                "rbId": rb.group(1),
                "itemId": item.group(1),
                "title": clean_title(html.unescape(title.group(1))),
                "author": html.unescape(author.group(1)).strip() if author else "",
                "price": int(price.group(1).replace(",", "")),
                "rating": float(rating.group(1)) if rating else None,
                "reviews": int(reviews.group(1)) if reviews else 0,
                "year": int(released.group(1)) if released else 0,
                "image": image_url(img.group(1)),
            }
        )
    return items


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    # シリーズ名などの括弧書きは省く（カードでは2行に収めたい）
    title = re.sub(r"\s*[（(][^）)]*(新書|文庫|ムック|教科書|シリーズ)[^）)]*[）)]\s*$", "", title)
    return title


def pick(items: list[dict], used: set[str], require: str, exclude: str) -> list[dict]:
    """楽天の売れ筋順のまま、話題に合う・評価の低くない・新しめの本だけを残す。"""
    chosen = []
    for item in items:
        if not item["image"] or item["year"] < MIN_YEAR or item["rbId"] in used:
            continue
        if item["rating"] is not None and item["rating"] < 3.5:
            continue
        if require and not re.search(require, item["title"], re.I):
            continue
        if exclude and re.search(exclude, item["title"], re.I):
            continue
        chosen.append(item)
        if len(chosen) >= PER_TOPIC:
            break
    return chosen


def partner_price(source: str) -> int | None:
    """提携先の商品価格を公式サイトから取り直す（値下げ・値上げに追従するため）。"""
    kind, _, ident = source.partition(":")
    try:
        if kind == "plaud":
            url = f"https://jp.plaud.ai/products/{ident}.js"
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return int(data["price"]) // 100
        if kind == "oz":
            url = f"https://www.ozgaming-pcshop.com/view/item/{ident}"
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                page = response.read().decode("utf-8", errors="ignore")
            match = re.search(r'makeshop-item-price:1">([\d,]+)', page)
            return int(match.group(1).replace(",", "")) if match else None
    except Exception as error:
        print(f"[partner] {source}: 価格取得失敗 {error}", file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--if-older-than", type=float, default=0, help="前回の取得からこの時間（h）未満なら何もしない")
    args = parser.parse_args()

    if args.if_older_than and PRODUCTS.exists():
        fetched = json.loads(PRODUCTS.read_text(encoding="utf-8")).get("fetchedAt")
        if fetched:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched)).total_seconds() / 3600
            if age < args.if_older_than:
                print(f"[books] 前回の取得から{age:.1f}時間なのでスキップ")
                return 0

    offers = json.loads(OFFERS.read_text(encoding="utf-8"))
    previous = json.loads(PRODUCTS.read_text(encoding="utf-8")) if PRODUCTS.exists() else {}
    result: dict[str, list[dict]] = {}
    used: set[str] = set()

    for topic in offers["topics"]:
        key, keyword = topic["key"], topic.get("search")
        if not keyword:
            continue
        try:
            items = parse(fetch(keyword))
        except Exception as error:  # 取得に失敗した話題は前回の結果を残す
            print(f"[books] {key}: 取得失敗 {error}", file=sys.stderr)
            result[key] = previous.get("books", {}).get(key, [])
            continue
        chosen = pick(items, used, topic.get("require", ""), topic.get("exclude", ""))
        used.update(item["rbId"] for item in chosen)
        result[key] = [
            {**item, "url": affiliate_url(item["rbId"], item["itemId"])} for item in chosen
        ]
        print(f"[books] {key} ({keyword}): {len(items)}件 → " + " / ".join(i["title"][:24] for i in chosen))
        time.sleep(1.5)

    partner_prices: dict[str, int] = {}
    for key, partner in offers.get("partners", {}).items():
        source = partner.get("source")
        if not source:
            continue
        price = partner_price(source)
        if price:
            partner_prices[key] = price
            print(f"[partner] {key}: {price:,}円")
        elif key in previous.get("partnerPrices", {}):
            partner_prices[key] = previous["partnerPrices"][key]

    output = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "pixel": PIXEL,
        "books": result,
        "partnerPrices": partner_prices,
    }
    if args.dry:
        print(json.dumps(output, ensure_ascii=False, indent=2)[:3000])
        return 0
    # 1件も取れなかったとき（楽天側の仕様変更など）は上書きしない
    if not any(result.values()):
        print("[books] 1件も取得できなかったため保存しません", file=sys.stderr)
        return 1
    PRODUCTS.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[books] saved {PRODUCTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
